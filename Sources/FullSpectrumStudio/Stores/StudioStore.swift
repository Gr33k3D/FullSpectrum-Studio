import AppKit
import Foundation
import SwiftUI
import UniformTypeIdentifiers

struct StudioErrorReport: Identifiable {
    let id = UUID()
    let message: String
    let details: String
    let logURL: URL?
}

@MainActor
final class StudioStore: ObservableObject {
    @Published var mode: PaletteMode = .official
    @Published var paletteSource: PaletteSource = .inventory
    @Published var realSlots: RealSlotSelection = .auto
    @Published var plannerMode: PlannerMode = .best
    @Published var planningSample: PlanningSample = .paint
    @Published var selectedMaterialFamilies: Set<String> = []
    @Published var pinnedAnchorKeys: Set<String> = []
    @Published var anchorSearch = ""
    @Published var mixPrediction: MixPrediction = .bambu
    @Published var qualityBias = 60.0
    @Published var previewMode: PreviewMode = .original
    @Published var viewerPerformance: ViewerPerformance = .balanced
    @Published var inventorySearch = ""
    @Published var inspection: ProjectInspection?
    @Published var result: ConversionResult?
    @Published var planPreview: PlanPreviewResult?
    @Published var inventory: InventorySnapshot?
    @Published var previewImage: NSImage?
    @Published var previewMeshURL: URL?
    @Published var outputPreviewMeshURL: URL?
    @Published var heatmapMeshURL: URL?
    @Published var anchorInfluenceMeshURL: URL?
    @Published var selectedFile: URL?
    @Published var referenceURL: URL?
    @Published var textureOverrideURL: URL?
    @Published var customPaletteURL: URL?
    @Published var status = "Drop a painted 3MF or textured model to begin."
    @Published var errorMessage: String?
    @Published var isWorking = false
    @Published var isPlanningPreview = false
    @Published var isBuildingPreview = false
    @Published var isRefreshingInventory = false
    @Published var progress = 0.0
    @Published var progressMessage = "Waiting for a model."
    @Published var activityMessages: [String] = ["Waiting for a model."]
    @Published var timingMessage = "No active estimate."
    @Published var errorReport: StudioErrorReport?
    @AppStorage("smartQuality") var smartQuality = true
    @AppStorage("catalogRegion") private var catalogRegionRawValue = CatalogRegion.global.rawValue
    @AppStorage("autoOpenValidatedOutput") var autoOpenValidatedOutput = true
    @AppStorage("outputApplication") private var outputApplicationRawValue = OutputApplication.bambuStudio.rawValue
    @AppStorage("restoreLastSession") var restoreLastSession = false
    @AppStorage("lastProjectPath") private var lastProjectPath = ""

    private let service = ConverterService()
    private var inspectionID = UUID()
    private var inspectionTask: Task<Void, Never>?
    private var previewTask: Task<Void, Never>?
    private var conversionID = UUID()
    private var conversionTask: Task<Void, Never>?
    private var planningTask: Task<Void, Never>?
    private var outputPreviewTask: Task<Void, Never>?
    private var activityMonitorTask: Task<Void, Never>?
    private var lastProgressDate = Date()
    private var lastEngineMessage = "Waiting for a model."
    private var operationStartedAt: Date?
    private var operationLabel = "Operation"
    private var operationHistoryKey: String?
    private var operationBroadHistoryKey: String?
    private var plannedDuration: TimeInterval?
    private var liveEstimatedTotal: TimeInterval?
    private var liveEstimateProgress = 0.0
    private var retainedSourceURL: URL?
    private var retainedSourceAccess = false
    private let immediateImportedPreviewByteLimit = 48 * 1024 * 1024
    private let runtimeHistoryDefaultsKey = "FullSpectrumRuntimeHistory.v2"
    private let maxRuntimeSamplesPerKey = 8

    var outputApplication: OutputApplication {
        get { OutputApplication(rawValue: outputApplicationRawValue) ?? .bambuStudio }
        set { outputApplicationRawValue = newValue.rawValue }
    }

    var catalogRegion: CatalogRegion {
        get { CatalogRegion(rawValue: catalogRegionRawValue) ?? .global }
        set { catalogRegionRawValue = newValue.rawValue }
    }

    var optionEstimateMessage: String {
        guard selectedFile != nil else {
            return "Open a source model to estimate plan and conversion time."
        }
        let plan = blendedDurationEstimate(kind: "plan")
        let conversion = blendedDurationEstimate(kind: "convert")
        let basis = hasRuntimeHistoryForCurrentOptions ? "local history + model size" : "model size + selected options"
        return "Estimate: Preview Plan \(formatDurationRange(plan)) • Compose \(formatDurationRange(conversion)) · \(basis)"
    }

    var anchorSelectionEnabled: Bool {
        mode == .official && [.inventory, .catalog, .allBambu].contains(paletteSource)
    }

    var materialFamilyOptions: [CatalogFamilyCount] {
        switch paletteSource {
        case .inventory:
            guard let inventory else { return [] }
            let grouped = Dictionary(grouping: inventory.spools, by: \.series)
            return grouped.map { CatalogFamilyCount(series: $0.key, count: $0.value.count) }
                .sorted { $0.series < $1.series }
        case .catalog:
            let core = Set(["PLA Basic", "PLA Matte", "PLA Silk+"])
            return inventory?.catalog?.families.filter { core.contains($0.series) } ?? []
        case .allBambu:
            return inventory?.catalog?.families ?? []
        case .custom, .exactCMYKW:
            return []
        }
    }

    var activeMaterialFamilies: [String] {
        let allowed = Set(materialFamilyOptions.map(\.series))
        return selectedMaterialFamilies
            .filter { allowed.contains($0) }
            .sorted()
    }

    var anchorCandidateOptions: [AnchorCandidate] {
        guard anchorSelectionEnabled, let inventory else { return [] }
        let base: [AnchorCandidate]
        switch paletteSource {
        case .inventory:
            base = inventory.spools.map {
                AnchorCandidate(
                    key: "\($0.series)|\($0.color)",
                    name: $0.name,
                    series: $0.series,
                    brand: $0.brand,
                    color: $0.color,
                    preset: $0.preset,
                    filamentID: $0.filamentID,
                    remainingGrams: $0.remainingGrams,
                    availability: "owned",
                    catalogSource: inventory.catalog?.source
                )
            }
        case .catalog, .allBambu:
            let core = Set(["PLA Basic", "PLA Matte", "PLA Silk+"])
            base = (inventory.anchorOptions ?? []).filter {
                paletteSource == .allBambu || core.contains($0.series)
            }
        case .custom, .exactCMYKW:
            base = []
        }
        let families = Set(activeMaterialFamilies)
        let familyFiltered = families.isEmpty ? base : base.filter { families.contains($0.series) }
        let query = anchorSearch.trimmingCharacters(in: .whitespacesAndNewlines)
        let searched = query.isEmpty ? familyFiltered : familyFiltered.filter {
            $0.name.localizedCaseInsensitiveContains(query)
            || $0.series.localizedCaseInsensitiveContains(query)
            || $0.color.localizedCaseInsensitiveContains(query)
        }
        return searched.sorted { lhs, rhs in
            if pinnedAnchorKeys.contains(lhs.key) != pinnedAnchorKeys.contains(rhs.key) {
                return pinnedAnchorKeys.contains(lhs.key)
            }
            if lhs.series != rhs.series { return lhs.series < rhs.series }
            return lhs.name < rhs.name
        }
    }

    var pinnedAnchorSummary: String {
        guard !pinnedAnchorKeys.isEmpty else { return "Auto recommends anchors" }
        return "\(pinnedAnchorKeys.count) pinned anchor\(pinnedAnchorKeys.count == 1 ? "" : "s")"
    }

    init() {
        refreshInventory()
        if restoreLastSession, !lastProjectPath.isEmpty {
            let restored = URL(fileURLWithPath: lastProjectPath)
            if FileManager.default.fileExists(atPath: restored.path) {
                Task { @MainActor in self.accept(url: restored) }
            }
        }
    }

    func refreshInventory() {
        isRefreshingInventory = true
        Task {
            do {
                inventory = try await service.inventory()
                pruneUnavailableSelections()
            } catch {
                present(error)
            }
            isRefreshingInventory = false
        }
    }

    func chooseSourceFile() {
        chooseFile(
            title: "Open Painted 3MF or Textured Model",
            message: "Choose a painted Bambu 3MF, or an experimental textured OBJ / GLB source.",
            extensions: ["3mf", "obj", "glb"],
            choosingStatus: "Choose a painted .3mf, textured .obj or .glb source."
        ) { [weak self] url in
            self?.accept(url: url)
        }
    }

    func chooseReferenceFile() {
        chooseFile(
            title: "Add Visual Reference",
            message: "Choose an OBJ, GLB or texture image used only as a visual target.",
            extensions: ["obj", "glb", "png", "jpg", "jpeg", "bmp", "tif", "tiff"],
            choosingStatus: "Choose an OBJ, GLB or texture image reference."
        ) { [weak self] url in
            self?.acceptReference(url: url)
        }
    }

    func chooseTextureFile() {
        chooseFile(
            title: "Choose OBJ Base-Color Texture",
            message: "Choose the PNG or JPEG base-color texture for the selected OBJ.",
            extensions: ["png", "jpg", "jpeg"],
            choosingStatus: "Choose the base-color texture for the OBJ."
        ) { [weak self] url in
            self?.acceptTextureOverride(url: url)
        }
    }

    func chooseCustomPaletteFile(startConversionAfterSelection: Bool = false, startPlanPreviewAfterSelection: Bool = false) {
        chooseFile(
            title: "Choose Filament Library",
            message: "Choose a local JSON file describing custom filament colors.",
            extensions: ["json"],
            choosingStatus: "Choose a custom filament JSON library."
        ) { [weak self] url in
            self?.acceptCustomPalette(url: url)
            if startConversionAfterSelection {
                self?.convert()
            } else if startPlanPreviewAfterSelection {
                self?.previewPlan()
            }
        }
    }

    private func chooseFile(
        title: String,
        message: String,
        extensions: [String],
        choosingStatus: String,
        acceptSelection: @escaping @MainActor (URL) -> Void
    ) {
        let previousStatus = status
        let panel = NSOpenPanel()
        panel.title = title
        panel.message = message
        panel.prompt = "Open"
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = extensions.compactMap { UTType(filenameExtension: $0) }
        status = choosingStatus
        NSApp.activate(ignoringOtherApps: true)
        panel.begin { [weak self] response in
            Task { @MainActor in
                guard let self else { return }
                guard response == .OK, let url = panel.url else {
                    if self.status == choosingStatus {
                        self.status = previousStatus
                    }
                    return
                }
                acceptSelection(url)
            }
        }
    }

    func accept(url: URL) {
        let extensionName = url.pathExtension.lowercased()
        if !["3mf", "obj", "glb"].contains(extensionName) {
            acceptReference(url: url)
            return
        }
        if selectedFile?.standardizedFileURL != url.standardizedFileURL || extensionName != "obj" {
            textureOverrideURL = nil
        }
        inspectionTask?.cancel()
        previewTask?.cancel()
        outputPreviewTask?.cancel()
        conversionID = UUID()
        conversionTask?.cancel()
        planningTask?.cancel()
        retainSelectedSourceAccess(to: url)
        selectedFile = url
        lastProjectPath = url.path
        let currentInspectionID = UUID()
        inspectionID = currentInspectionID
        inspection = nil
        result = nil
        planPreview = nil
        previewImage = nil
        previewMeshURL = nil
        outputPreviewMeshURL = nil
        heatmapMeshURL = nil
        anchorInfluenceMeshURL = nil
        previewMode = .original
        isBuildingPreview = true
        isPlanningPreview = false
        progress = 0
        progressMessage = "Reading model metadata."
        activityMessages = ["Reading model metadata."]
        startOperationTiming(
            "Preview",
            plannedDuration: blendedDurationEstimate(kind: "preview"),
            historyKey: estimateHistoryKey(kind: "preview"),
            broadHistoryKey: broadEstimateHistoryKey(kind: "preview")
        )
        errorMessage = nil
        errorReport = nil
        status = ["obj", "glb"].contains(extensionName)
            ? "Opening textured source and analyzing paint colors..."
            : "Reading project preview and material slots..."
        isWorking = false
        let previewURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-\(UUID().uuidString).png")
        let generatedMeshURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-\(UUID().uuidString).obj")
        let capturedTextureOverride = textureOverrideURL

        if extensionName == "3mf" {
            inspectionTask = Task {
                do {
                    let project = try await service.metadata(file: url, thumbnailURL: previewURL)
                    guard inspectionID == currentInspectionID else { return }
                    inspection = project
                    previewImage = project.thumbnail.flatMap { NSImage(contentsOfFile: $0) }
                    plannedDuration = blendedDurationEstimate(kind: "preview")
                    liveEstimatedTotal = plannedDuration
                    operationHistoryKey = estimateHistoryKey(kind: "preview")
                    updateTimingEstimate()
                    status = "\(project.sourceSlots) source filaments loaded. Preparing an efficient 3D preview..."
                    buildInteractivePreview(
                        for: url,
                        outputURL: generatedMeshURL,
                        inspectionID: currentInspectionID,
                        textureOverride: nil,
                        keepExistingMesh: false
                    )
                } catch is CancellationError {
                    return
                } catch {
                    guard inspectionID == currentInspectionID else { return }
                    present(error)
                    status = "Could not open that project."
                    isBuildingPreview = false
                }
                if inspectionID == currentInspectionID {
                    inspectionTask = nil
                }
            }
            return
        }

        if canDisplayImportedSourceImmediately(url) {
            previewMeshURL = url
            status = "Source geometry opened. Sampling texture colors in the background..."
        } else {
            status = "Large textured source selected. Building a bounded preview in the background..."
        }
        buildInteractivePreview(
            for: url,
            outputURL: generatedMeshURL,
            inspectionID: currentInspectionID,
            textureOverride: capturedTextureOverride,
            keepExistingMesh: previewMeshURL != nil
        )
    }

    private func canDisplayImportedSourceImmediately(_ url: URL) -> Bool {
        guard let bytes = try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize else {
            return false
        }
        return bytes <= immediateImportedPreviewByteLimit
    }

    private func buildInteractivePreview(
        for url: URL,
        outputURL: URL,
        inspectionID currentInspectionID: UUID,
        textureOverride: URL?,
        keepExistingMesh: Bool
    ) {
        previewTask?.cancel()
        isBuildingPreview = true
        startActivityMonitor(label: "Preview")
        previewTask = Task {
            let temporaryAccess = beginTemporaryAccess(to: [textureOverride])
            defer { endTemporaryAccess(temporaryAccess) }
            do {
                let project = try await service.previewMesh(
                    file: url,
                    outputURL: outputURL,
                    mixPrediction: mixPrediction,
                    textureOverride: textureOverride,
                    progress: { [weak self] value, message in
                        Task { @MainActor in
                            guard self?.inspectionID == currentInspectionID else { return }
                            self?.recordProgress(value, message)
                        }
                    }
                )
                guard inspectionID == currentInspectionID else { return }
                inspection = project
                if let thumbnail = project.thumbnail {
                    previewImage = NSImage(contentsOfFile: thumbnail)
                }
                if let mesh = project.previewMesh {
                    previewMeshURL = URL(fileURLWithPath: mesh)
                } else if !keepExistingMesh {
                    previewMeshURL = nil
                }
                if let recommendation = project.metrics?.recommendedRenderMode,
                   let mode = ViewerPerformance(rawValue: recommendation) {
                    viewerPerformance = mode
                }
                plannedDuration = blendedDurationEstimate(kind: "preview")
                liveEstimatedTotal = plannedDuration
                operationHistoryKey = estimateHistoryKey(kind: "preview")
                updateTimingEstimate()
                status = project.previewNotice ?? "\(project.sourceSlots) source filaments ready for conversion."
            } catch is CancellationError {
                return
            } catch {
                guard inspectionID == currentInspectionID else { return }
                present(error)
                status = "Could not open that project."
            }
            if inspectionID == currentInspectionID {
                isBuildingPreview = false
                progress = 0
                progressMessage = "Ready for conversion."
                finishOperationTiming("Preview ready")
                previewTask = nil
                stopActivityMonitorIfIdle()
            }
        }
    }

    func acceptReference(url: URL) {
        let supported = ["obj", "glb", "png", "jpg", "jpeg", "bmp", "tif", "tiff"]
        guard supported.contains(url.pathExtension.lowercased()) else {
            present(message: "Reference mode accepts OBJ, GLB or a texture image.")
            return
        }
        referenceURL = url
        result = nil
        planPreview = nil
        status = "Reference selected: \(url.lastPathComponent). Load or convert a 3MF to score it."
    }

    func toggleMaterialFamily(_ series: String) {
        if selectedMaterialFamilies.contains(series) {
            selectedMaterialFamilies.remove(series)
        } else {
            selectedMaterialFamilies.insert(series)
        }
        planPreview = nil
        pruneUnavailableSelections()
    }

    func clearMaterialFamilies() {
        selectedMaterialFamilies.removeAll()
        planPreview = nil
        pruneUnavailableSelections()
    }

    func toggleAnchorPin(_ candidate: AnchorCandidate) {
        if pinnedAnchorKeys.contains(candidate.key) {
            pinnedAnchorKeys.remove(candidate.key)
        } else {
            pinnedAnchorKeys.insert(candidate.key)
        }
        planPreview = nil
    }

    func clearAnchorPins() {
        pinnedAnchorKeys.removeAll()
        planPreview = nil
    }

    func useRecommendedAnchors() {
        let anchors = planPreview?.anchors ?? result?.anchors ?? []
        let keys = anchors.compactMap(\.key)
        guard !keys.isEmpty else { return }
        pinnedAnchorKeys = Set(keys)
        planPreview = nil
        status = "Pinned \(keys.count) recommended Bambu anchors. Preview or compose again to lock them in."
    }

    func plannerInputsChanged() {
        planPreview = nil
        pruneUnavailableSelections()
    }

    func acceptCustomPalette(url: URL) {
        guard url.pathExtension.lowercased() == "json" else {
            present(message: "Custom filament libraries must be JSON files.")
            return
        }
        customPaletteURL = url
        paletteSource = .custom
        result = nil
        planPreview = nil
    }

    func acceptTextureOverride(url: URL) {
        guard ["png", "jpg", "jpeg"].contains(url.pathExtension.lowercased()) else {
            present(message: "OBJ import textures must be PNG or JPEG files.")
            return
        }
        textureOverrideURL = url
        result = nil
        planPreview = nil
        if let selectedFile, selectedFile.pathExtension.lowercased() == "obj" {
            accept(url: selectedFile)
        }
    }

    func previewPlan() {
        guard let file = selectedFile else {
            chooseSourceFile()
            return
        }
        if paletteSource == .custom && customPaletteURL == nil {
            chooseCustomPaletteFile(startPlanPreviewAfterSelection: true)
            return
        }
        isPlanningPreview = true
        isWorking = false
        errorMessage = nil
        errorReport = nil
        result = nil
        planPreview = nil
        progress = 0
        progressMessage = "Starting palette plan preview."
        activityMessages = ["Starting palette plan preview."]
        startOperationTiming(
            "Plan preview",
            plannedDuration: blendedDurationEstimate(kind: "plan"),
            historyKey: estimateHistoryKey(kind: "plan"),
            broadHistoryKey: broadEstimateHistoryKey(kind: "plan")
        )
        status = planningSample == .preview
            ? "Previewing palette with optimized preview-mesh color weights..."
            : "Previewing palette with original paint-state weights..."
        inspectionTask?.cancel()
        previewTask?.cancel()
        outputPreviewTask?.cancel()
        isBuildingPreview = false
        planningTask?.cancel()
        conversionTask?.cancel()
        let currentConversionID = UUID()
        conversionID = currentConversionID
        let capturedMode = mode
        let capturedPaletteSource = paletteSource
        let capturedRealSlots = realSlots
        let capturedReference = referenceURL
        let capturedPalette = customPaletteURL
        let capturedTexture = textureOverrideURL
        let capturedPrediction = mixPrediction
        let capturedPlannerMode = plannerMode
        let capturedPlanningSample = planningSample
        let capturedMaterialFamilies = activeMaterialFamilies
        let capturedPinnedAnchors = anchorSelectionEnabled ? pinnedAnchorKeys.sorted() : []
        let capturedSmartQuality = smartQuality
        let capturedQualityBias = Int(qualityBias)
        let capturedCatalogRegion = catalogRegion
        startActivityMonitor(label: "Plan preview")
        planningTask = Task {
            let temporaryAccess = beginTemporaryAccess(to: [capturedReference, capturedPalette, capturedTexture])
            defer { endTemporaryAccess(temporaryAccess) }
            do {
                let preview = try await service.planPreview(
                    file: file,
                    mode: capturedMode,
                    paletteSource: capturedPaletteSource,
                    realSlots: capturedRealSlots,
                    reference: capturedReference,
                    customPalette: capturedPalette,
                    textureOverride: capturedTexture,
                    qualityBias: capturedSmartQuality ? "auto" : String(capturedQualityBias),
                    catalogRegion: capturedCatalogRegion,
                    plannerMode: capturedPlannerMode,
                    planningSample: capturedPlanningSample,
                    materialFamilies: capturedMaterialFamilies,
                    pinnedAnchorKeys: capturedPinnedAnchors,
                    mixPrediction: capturedPrediction,
                    outputDirectory: file.deletingLastPathComponent(),
                    progress: { [weak self] value, message in
                        Task { @MainActor in
                            guard self?.conversionID == currentConversionID else { return }
                            self?.recordProgress(value, message)
                        }
                    }
                )
                guard conversionID == currentConversionID else { return }
                planPreview = preview
                progress = 1
                progressMessage = "Plan preview ready."
                finishOperationTiming("Plan preview ready")
                status = "Preview plan: \(preview.realSlots) physical and \(preview.outputSlots - preview.realSlots) mixed slots. No 3MF was written."
            } catch is CancellationError {
                guard conversionID == currentConversionID else { return }
                status = "Plan preview cancelled."
                progressMessage = "Cancelled."
                finishOperationTiming("Cancelled")
            } catch {
                guard conversionID == currentConversionID else { return }
                present(error)
                status = "Plan preview failed."
                progressMessage = "Plan preview failed."
                finishOperationTiming("Failed")
            }
            if conversionID == currentConversionID {
                isPlanningPreview = false
                planningTask = nil
                stopActivityMonitorIfIdle()
            }
        }
    }

    func convert() {
        guard let file = selectedFile else {
            chooseSourceFile()
            return
        }
        if paletteSource == .custom && customPaletteURL == nil {
            chooseCustomPaletteFile(startConversionAfterSelection: true)
            return
        }
        isWorking = true
        isPlanningPreview = false
        errorMessage = nil
        errorReport = nil
        planPreview = nil
        progress = 0
        progressMessage = "Starting conversion."
        activityMessages = ["Starting conversion."]
        startOperationTiming(
            "Conversion",
            plannedDuration: blendedDurationEstimate(kind: "convert"),
            historyKey: estimateHistoryKey(kind: "convert"),
            broadHistoryKey: broadEstimateHistoryKey(kind: "convert")
        )
        status = plannerMode == .best
            ? "Deep Best planner is searching anchors and Bambu mix recipes..."
            : "Converting painted facets and validating the output..."
        inspectionTask?.cancel()
        previewTask?.cancel()
        outputPreviewTask?.cancel()
        isBuildingPreview = false
        conversionTask?.cancel()
        planningTask?.cancel()
        let currentConversionID = UUID()
        conversionID = currentConversionID
        let capturedMode = mode
        let capturedPaletteSource = paletteSource
        let capturedRealSlots = realSlots
        let capturedReference = referenceURL
        let capturedPalette = customPaletteURL
        let capturedTexture = textureOverrideURL
        let capturedPrediction = mixPrediction
        let capturedPlannerMode = plannerMode
        let capturedPlanningSample = planningSample
        let capturedMaterialFamilies = activeMaterialFamilies
        let capturedPinnedAnchors = anchorSelectionEnabled ? pinnedAnchorKeys.sorted() : []
        let capturedSmartQuality = smartQuality
        let capturedQualityBias = Int(qualityBias)
        let capturedCatalogRegion = catalogRegion
        startActivityMonitor(label: capturedPlannerMode == .best ? "Best planner" : "Conversion")
        conversionTask = Task {
            let temporaryAccess = beginTemporaryAccess(to: [capturedReference, capturedPalette, capturedTexture])
            defer { endTemporaryAccess(temporaryAccess) }
            do {
                let converted = try await service.convert(
                    file: file,
                    mode: capturedMode,
                    paletteSource: capturedPaletteSource,
                    realSlots: capturedRealSlots,
                    reference: capturedReference,
                    customPalette: capturedPalette,
                    textureOverride: capturedTexture,
                    qualityBias: capturedSmartQuality ? "auto" : String(capturedQualityBias),
                    catalogRegion: capturedCatalogRegion,
                    plannerMode: capturedPlannerMode,
                    planningSample: capturedPlanningSample,
                    materialFamilies: capturedMaterialFamilies,
                    pinnedAnchorKeys: capturedPinnedAnchors,
                    mixPrediction: capturedPrediction,
                    outputDirectory: file.deletingLastPathComponent(),
                    progress: { [weak self] value, message in
                        Task { @MainActor in
                            guard self?.conversionID == currentConversionID else { return }
                            self?.recordProgress(value, message)
                        }
                    }
                )
                guard conversionID == currentConversionID else { return }
                result = converted
                inventory = converted.inventory
                outputPreviewMeshURL = converted.analysisAssets?.predictedMesh.map(URL.init(fileURLWithPath:))
                heatmapMeshURL = converted.analysisAssets?.heatmapMesh.map(URL.init(fileURLWithPath:))
                anchorInfluenceMeshURL = converted.analysisAssets?.anchorInfluenceMesh.map(URL.init(fileURLWithPath:))
                if outputPreviewMeshURL != nil {
                    previewMode = .predicted
                }
                progress = 1
                progressMessage = "Validated output is ready."
                finishOperationTiming("Validated")
                let qualitySuffix = converted.quality.qualityBiasMode == "auto"
                    ? converted.quality.resolvedQualityBias.map { " Smart quality \($0)/100." } ?? ""
                    : ""
                status = "Validated: \(converted.realSlots) physical and \(converted.outputSlots - converted.realSlots) mixed slots.\(qualitySuffix)"
                if outputPreviewMeshURL == nil {
                    buildOutputPreview(for: converted.output, conversionID: currentConversionID, mixPrediction: capturedPrediction)
                }
                if autoOpenValidatedOutput {
                    openOutput()
                }
            } catch is CancellationError {
                guard conversionID == currentConversionID else { return }
                status = "Conversion cancelled."
                progressMessage = "Cancelled."
                finishOperationTiming("Cancelled")
            } catch {
                guard conversionID == currentConversionID else { return }
                outputPreviewTask?.cancel()
                outputPreviewTask = nil
                present(error)
                status = "Conversion failed."
                progressMessage = "Conversion failed."
                finishOperationTiming("Failed")
            }
            if conversionID == currentConversionID {
                isWorking = false
                conversionTask = nil
                stopActivityMonitorIfIdle()
            }
        }
    }

    func cancelConversion() {
        inspectionTask?.cancel()
        previewTask?.cancel()
        outputPreviewTask?.cancel()
        inspectionID = UUID()
        conversionID = UUID()
        conversionTask?.cancel()
        planningTask?.cancel()
        inspectionTask = nil
        previewTask = nil
        outputPreviewTask = nil
        conversionTask = nil
        planningTask = nil
        isWorking = false
        isPlanningPreview = false
        isBuildingPreview = false
        status = "Conversion cancelled."
        progressMessage = "Cancelled."
        recordActivity("Cancelled.")
        finishOperationTiming("Cancelled")
        stopActivityMonitorIfIdle()
    }

    func cancelPreview() {
        inspectionTask?.cancel()
        previewTask?.cancel()
        inspectionID = UUID()
        inspectionTask = nil
        previewTask = nil
        isBuildingPreview = false
        progress = 0
        progressMessage = "Preview stopped."
        recordActivity("Preview stopped.")
        finishOperationTiming("Stopped")
        status = inspection == nil ? "Preview stopped. Choose a source to try again." : "Ready for conversion. Interactive preview stopped."
        stopActivityMonitorIfIdle()
    }

    func cancelActiveOperation() {
        if isWorking {
            cancelConversion()
        } else if isPlanningPreview {
            cancelPlanPreview()
        } else if isBuildingPreview {
            cancelPreview()
        }
    }

    func cancelPlanPreview() {
        planningTask?.cancel()
        conversionID = UUID()
        planningTask = nil
        isPlanningPreview = false
        progress = 0
        progressMessage = "Plan preview stopped."
        recordActivity("Plan preview stopped.")
        finishOperationTiming("Stopped")
        status = selectedFile == nil ? "Plan preview stopped. Choose a source to try again." : "Ready for conversion. Plan preview stopped."
        stopActivityMonitorIfIdle()
    }

    private func buildOutputPreview(for path: String, conversionID currentConversionID: UUID, mixPrediction: MixPrediction) {
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-Predicted-\(UUID().uuidString).obj")
        outputPreviewTask?.cancel()
        outputPreviewTask = Task {
            do {
                let project = try await service.previewMesh(
                    file: URL(fileURLWithPath: path),
                    outputURL: outputURL,
                    mixPrediction: mixPrediction,
                    textureOverride: textureOverrideURL
                )
                guard conversionID == currentConversionID, result?.output == path else { return }
                outputPreviewMeshURL = project.previewMesh.map(URL.init(fileURLWithPath:))
            } catch {
                guard conversionID == currentConversionID, result?.output == path else { return }
                outputPreviewMeshURL = nil
            }
            if conversionID == currentConversionID {
                outputPreviewTask = nil
            }
        }
    }

    private func retainSelectedSourceAccess(to url: URL) {
        if retainedSourceAccess, let retainedSourceURL {
            retainedSourceURL.stopAccessingSecurityScopedResource()
        }
        retainedSourceURL = url
        retainedSourceAccess = url.startAccessingSecurityScopedResource()
    }

    private func beginTemporaryAccess(to urls: [URL?]) -> [URL] {
        var opened: [URL] = []
        var visited = Set<String>()
        for url in urls.compactMap({ $0 }) {
            let path = url.standardizedFileURL.path
            guard visited.insert(path).inserted,
                  retainedSourceURL?.standardizedFileURL.path != path else {
                continue
            }
            if url.startAccessingSecurityScopedResource() {
                opened.append(url)
            }
        }
        return opened
    }

    private func endTemporaryAccess(_ urls: [URL]) {
        urls.forEach { $0.stopAccessingSecurityScopedResource() }
    }

    func revealOutput() {
        guard let path = result?.output else { return }
        let outputURL = URL(fileURLWithPath: path)
        guard FileManager.default.fileExists(atPath: outputURL.path) else {
            present(message: "The validated output file could not be found.")
            return
        }
        if !NSWorkspace.shared.selectFile(outputURL.path, inFileViewerRootedAtPath: "") {
            NSWorkspace.shared.open(outputURL.deletingLastPathComponent())
        }
    }

    func openOutput() {
        guard let path = result?.output else { return }
        let outputURL = URL(fileURLWithPath: path)
        guard FileManager.default.fileExists(atPath: outputURL.path) else {
            present(message: "The validated output file could not be found.")
            return
        }
        switch outputApplication {
        case .bambuStudio:
            if let applicationURL = installedApplication(
                bundleIdentifiers: ["com.bambulab.bambu-studio"],
                applicationNames: ["BambuStudio.app"]
            ) {
                open(outputURL, with: applicationURL, named: "Bambu Studio")
            } else if !NSWorkspace.shared.open(outputURL) {
                present(message: "Could not open the validated output in its default application.")
            }
        case .orcaSlicer:
            guard let applicationURL = installedApplication(
                bundleIdentifiers: ["com.softfever3d.orca-slicer", "com.orcaslicer.OrcaSlicer"],
                applicationNames: ["OrcaSlicer.app", "Orca Slicer.app"]
            ) else {
                present(message: "OrcaSlicer is not installed. The validated output is saved and can be opened manually after installing OrcaSlicer.")
                return
            }
            open(outputURL, with: applicationURL, named: "OrcaSlicer")
        }
    }

    func openColorValidationReport() {
        guard let path = result?.colorValidationReport else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    private func installedApplication(bundleIdentifiers: [String], applicationNames: [String]) -> URL? {
        for identifier in bundleIdentifiers {
            if let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: identifier) {
                return url
            }
        }
        let roots = [URL(fileURLWithPath: "/Applications", isDirectory: true),
                     URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Applications", isDirectory: true)]
        for root in roots {
            for name in applicationNames {
                let candidate = root.appendingPathComponent(name, isDirectory: true)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    return candidate
                }
            }
        }
        return nil
    }

    private func open(_ outputURL: URL, with applicationURL: URL, named name: String) {
        let configuration = NSWorkspace.OpenConfiguration()
        NSWorkspace.shared.open([outputURL], withApplicationAt: applicationURL, configuration: configuration) { [weak self] _, error in
            guard let error else { return }
            Task { @MainActor in
                self?.present(message: "Could not open the validated output in \(name): \(error.localizedDescription)")
            }
        }
    }

    func clearError() {
        errorMessage = nil
        errorReport = nil
    }

    func copyErrorReport() {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(errorReport?.details ?? errorMessage ?? "", forType: .string)
    }

    func openErrorLog() {
        guard let logURL = errorReport?.logURL else { return }
        NSWorkspace.shared.open(logURL)
    }

    private func present(_ error: Error) {
        let message = error.localizedDescription
        errorMessage = message
        if let converterError = error as? ConverterError,
           let debugReport = converterError.debugReport {
            errorReport = StudioErrorReport(message: message, details: debugReport, logURL: converterError.logURL)
        } else {
            errorReport = StudioErrorReport(message: message, details: message, logURL: nil)
        }
    }

    private func present(message: String) {
        errorMessage = message
        errorReport = StudioErrorReport(message: message, details: message, logURL: nil)
    }

    private func recordProgress(_ value: Double, _ message: String) {
        progress = value
        progressMessage = message
        lastProgressDate = Date()
        lastEngineMessage = message
        recordActivity(message)
        updateTimingEstimate()
    }

    private func startOperationTiming(_ label: String, plannedDuration: TimeInterval?, historyKey: String?, broadHistoryKey: String?) {
        operationStartedAt = Date()
        operationLabel = label
        operationHistoryKey = historyKey
        operationBroadHistoryKey = broadHistoryKey
        self.plannedDuration = plannedDuration
        liveEstimatedTotal = plannedDuration
        liveEstimateProgress = progress
        updateTimingEstimate()
    }

    private func finishOperationTiming(_ finalState: String) {
        guard let started = operationStartedAt else {
            timingMessage = "No active estimate."
            return
        }
        let elapsed = Date().timeIntervalSince(started)
        recordRuntimeSampleIfUseful(finalState: finalState, seconds: elapsed)
        timingMessage = "\(finalState) in \(formatDuration(elapsed))."
        operationStartedAt = nil
        plannedDuration = nil
        operationHistoryKey = nil
        operationBroadHistoryKey = nil
        liveEstimatedTotal = nil
        liveEstimateProgress = 0
    }

    private func updateTimingEstimate(now: Date = Date()) {
        guard let started = operationStartedAt else {
            timingMessage = "No active estimate."
            return
        }
        let elapsed = max(0, now.timeIntervalSince(started))
        let estimate = estimatedTotalDuration(elapsed: elapsed)
        if let estimate {
            if elapsed > estimate + 8 {
                timingMessage = "\(operationLabel): elapsed \(formatDuration(elapsed)) • running longer than expected • still working at \(Int(progress * 100))%"
            } else {
                let remaining = max(0, estimate - elapsed)
                timingMessage = "\(operationLabel): elapsed \(formatDuration(elapsed)) • about \(formatDuration(remaining)) left • estimate \(formatDuration(estimate))"
            }
        } else if let plannedDuration {
            let remaining = max(0, plannedDuration - elapsed)
            timingMessage = "\(operationLabel): elapsed \(formatDuration(elapsed)) • about \(formatDuration(remaining)) left • planned \(formatDuration(plannedDuration))"
        } else {
            timingMessage = "\(operationLabel): elapsed \(formatDuration(elapsed)) • estimating remaining time"
        }
    }

    private func estimatedTotalDuration(elapsed: TimeInterval) -> TimeInterval? {
        let minimumRemaining = minimumRemainingForCurrentProgress()
        guard progress > 0.035 else {
            return liveEstimatedTotal ?? plannedDuration
        }

        guard progress > liveEstimateProgress + 0.015 else {
            if let current = liveEstimatedTotal ?? plannedDuration,
               elapsed > current - 6 {
                liveEstimatedTotal = max(current, elapsed + minimumRemaining)
            }
            return liveEstimatedTotal ?? plannedDuration
        }

        let progressEstimate = elapsed / min(max(progress, 0.04), 0.98)

        if let current = liveEstimatedTotal ?? plannedDuration {
            let weighted = progressEstimate < current
                ? (current * 0.50 + progressEstimate * 0.50)
                : (current * 0.78 + progressEstimate * 0.22)
            let maxStepUp = current + max(12, current * 0.14)
            liveEstimatedTotal = max(elapsed + minimumRemaining, min(weighted, maxStepUp))
        } else {
            liveEstimatedTotal = max(elapsed + minimumRemaining, progressEstimate)
        }
        liveEstimateProgress = progress
        return liveEstimatedTotal
    }

    private func minimumRemainingForCurrentProgress() -> TimeInterval {
        if progress < 0.45 {
            return 25
        }
        if progress < 0.85 {
            return 14
        }
        return 6
    }

    private func expectedPlannerDuration(planOnly: Bool) -> TimeInterval? {
        var seconds: TimeInterval
        switch plannerMode {
        case .fast:
            seconds = planOnly ? 18 : 38
        case .best:
            seconds = smartQuality ? (planOnly ? 95 : 170) : (planOnly ? 52 : 108)
        }
        if planningSample == .preview {
            seconds *= 1.2
        }
        switch paletteSource {
        case .allBambu:
            seconds *= 1.12
        case .catalog:
            seconds *= 0.92
        case .inventory where (inventory?.spools.count ?? 0) <= 24:
            seconds *= 0.84
        default:
            break
        }
        if !activeMaterialFamilies.isEmpty {
            seconds *= 0.84
        }
        if !pinnedAnchorKeys.isEmpty {
            seconds *= 0.78
        }
        if realSlots != .auto {
            seconds *= 0.90
        }
        if let metrics = inspection?.metrics {
            let baseline = planningSample == .preview ? 650_000.0 : 1_100_000.0
            let ceiling = planningSample == .preview ? 4.0 : 2.2
            let triangleScale = min(ceiling, max(0.65, Double(metrics.triangleCount) / baseline))
            seconds *= triangleScale
        } else if selectedFile?.pathExtension.lowercased() == "obj" || selectedFile?.pathExtension.lowercased() == "glb" {
            seconds *= 2.0
        }
        return seconds
    }

    private func blendedDurationEstimate(kind: String) -> TimeInterval? {
        let heuristic = heuristicDurationEstimate(kind: kind)
        let exactHistory = runtimeHistoryEstimate(for: estimateHistoryKey(kind: kind))
        let broadHistory = runtimeHistoryEstimate(for: broadEstimateHistoryKey(kind: kind))

        switch (heuristic, exactHistory, broadHistory) {
        case let (heuristic?, exact?, _):
            return heuristic * 0.58 + exact * 0.42
        case let (heuristic?, nil, broad?):
            return heuristic * 0.74 + broad * 0.26
        case let (heuristic?, nil, nil):
            return heuristic
        case let (nil, exact?, _):
            return exact
        case let (nil, nil, broad?):
            return broad
        default:
            return nil
        }
    }

    private func heuristicDurationEstimate(kind: String) -> TimeInterval? {
        switch kind {
        case "preview":
            if let estimate = inspection?.metrics?.previewBuildEstimateSeconds {
                return estimate
            }
            guard let selectedFile else { return nil }
            let fileSize = fileSizeBytes(for: selectedFile)
            let megabytes = Double(fileSize ?? 24_000_000) / 1_000_000.0
            let fileMultiplier = selectedFile.pathExtension.lowercased() == "3mf" ? 1.0 : 1.55
            return min(240, max(12, 10 + megabytes * 1.15 * fileMultiplier))
        case "plan":
            return expectedPlannerDuration(planOnly: true)
        case "convert":
            return expectedPlannerDuration(planOnly: false)
        default:
            return nil
        }
    }

    private var hasRuntimeHistoryForCurrentOptions: Bool {
        ["plan", "convert"].contains { kind in
            runtimeHistoryEstimate(for: estimateHistoryKey(kind: kind)) != nil
        }
    }

    private func estimateHistoryKey(kind: String) -> String {
        if kind == "preview" {
            return ["preview", modelComplexityBucket(), selectedFile?.pathExtension.lowercased() ?? "none"].joined(separator: "|")
        }
        let qualityBucket = smartQuality ? "smart" : "q\(Int((qualityBias / 20.0).rounded()) * 20)"
        let slotBucket = realSlots == .auto ? "auto" : "manual-\(realSlots.rawValue)"
        let materialBucket = activeMaterialFamilies.isEmpty ? "all-materials" : activeMaterialFamilies.joined(separator: "+")
        let anchorBucket = pinnedAnchorKeys.isEmpty ? "auto-anchors" : "pins-\(pinnedAnchorKeys.sorted().joined(separator: "+"))"
        return [
            kind,
            modelComplexityBucket(),
            plannerMode.rawValue,
            planningSample.rawValue,
            qualityBucket,
            mode.rawValue,
            paletteSource.rawValue,
            slotBucket,
            materialBucket,
            anchorBucket
        ].joined(separator: "|")
    }

    private func broadEstimateHistoryKey(kind: String) -> String {
        [
            "broad",
            kind,
            modelComplexityBucket(),
            plannerMode.rawValue,
            planningSample.rawValue,
            smartQuality ? "smart" : "manual",
            activeMaterialFamilies.isEmpty ? "all-materials" : activeMaterialFamilies.joined(separator: "+"),
            pinnedAnchorKeys.isEmpty ? "auto-anchors" : "manual-anchors"
        ].joined(separator: "|")
    }

    private func pruneUnavailableSelections() {
        let allowedFamilies = Set(materialFamilyOptions.map(\.series))
        selectedMaterialFamilies = selectedMaterialFamilies.filter { allowedFamilies.contains($0) }
        guard anchorSelectionEnabled else {
            pinnedAnchorKeys.removeAll()
            return
        }
        let availableKeys = Set(anchorCandidateOptions.map(\.key))
        pinnedAnchorKeys = pinnedAnchorKeys.filter { availableKeys.contains($0) }
    }

    private func modelComplexityBucket() -> String {
        if let triangles = inspection?.metrics?.triangleCount {
            switch triangles {
            case ..<80_000: return "tri-xs"
            case ..<250_000: return "tri-sm"
            case ..<700_000: return "tri-md"
            case ..<1_500_000: return "tri-lg"
            default: return "tri-xl"
            }
        }
        if let selectedFile,
           let bytes = fileSizeBytes(for: selectedFile) {
            switch bytes {
            case ..<12_000_000: return "file-xs"
            case ..<45_000_000: return "file-sm"
            case ..<120_000_000: return "file-md"
            case ..<300_000_000: return "file-lg"
            default: return "file-xl"
            }
        }
        return "unknown"
    }

    private func fileSizeBytes(for url: URL) -> Int? {
        try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize
    }

    private func recordRuntimeSampleIfUseful(finalState: String, seconds: TimeInterval) {
        let lower = finalState.lowercased()
        guard !lower.contains("cancel"),
              !lower.contains("fail"),
              !lower.contains("stop"),
              seconds >= 2,
              let exactKey = operationHistoryKey else {
            return
        }
        appendRuntimeSample(seconds, to: exactKey)
        if let broadKey = operationBroadHistoryKey {
            appendRuntimeSample(seconds, to: broadKey)
        }
    }

    private func appendRuntimeSample(_ seconds: TimeInterval, to key: String) {
        var history = runtimeHistory()
        var samples = history[key] ?? []
        samples.append(seconds)
        if samples.count > maxRuntimeSamplesPerKey {
            samples.removeFirst(samples.count - maxRuntimeSamplesPerKey)
        }
        history[key] = samples
        if let data = try? JSONEncoder().encode(history) {
            UserDefaults.standard.set(data, forKey: runtimeHistoryDefaultsKey)
        }
    }

    private func runtimeHistoryEstimate(for key: String) -> TimeInterval? {
        guard let samples = runtimeHistory()[key], !samples.isEmpty else { return nil }
        let sorted = samples.sorted()
        if sorted.count % 2 == 1 {
            return sorted[sorted.count / 2]
        }
        let upper = sorted.count / 2
        return (sorted[upper - 1] + sorted[upper]) / 2.0
    }

    private func runtimeHistory() -> [String: [Double]] {
        guard let data = UserDefaults.standard.data(forKey: runtimeHistoryDefaultsKey),
              let decoded = try? JSONDecoder().decode([String: [Double]].self, from: data) else {
            return [:]
        }
        return decoded
    }

    private func formatDurationRange(_ seconds: TimeInterval?) -> String {
        guard let seconds else { return "after model load" }
        let low = max(2, seconds * 0.72)
        let high = max(low + 4, seconds * 1.35)
        return "\(formatDuration(low))-\(formatDuration(high))"
    }

    private func formatDuration(_ seconds: TimeInterval) -> String {
        let rounded = max(0, Int(seconds.rounded()))
        if rounded < 60 {
            return "\(rounded)s"
        }
        let minutes = rounded / 60
        let secondsRemainder = rounded % 60
        if minutes < 60 {
            return secondsRemainder == 0 ? "\(minutes)m" : "\(minutes)m \(secondsRemainder)s"
        }
        let hours = minutes / 60
        let minutesRemainder = minutes % 60
        return minutesRemainder == 0 ? "\(hours)h" : "\(hours)h \(minutesRemainder)m"
    }

    private func recordActivity(_ message: String) {
        guard !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        if activityMessages.last != message {
            activityMessages.append(message)
        }
        if activityMessages.count > 8 {
            activityMessages.removeFirst(activityMessages.count - 8)
        }
    }

    private func startActivityMonitor(label: String) {
        lastProgressDate = Date()
        lastEngineMessage = progressMessage
        activityMonitorTask?.cancel()
        activityMonitorTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 5_000_000_000)
                guard let self else { return }
                let idleSeconds = Date().timeIntervalSince(self.lastProgressDate)
                guard self.isWorking || self.isBuildingPreview || self.isPlanningPreview else { return }
                if idleSeconds >= 90 {
                    if label == "Best planner" {
                        self.status = "Best planner is still deep-searching. You can switch to Fast or cancel if you need a quick pass."
                        self.progressMessage = "Deep search still working: \(self.lastEngineMessage)"
                    } else if label == "Plan preview" {
                        self.status = "Plan preview is still searching. You can cancel or switch Planner to Fast for a quicker estimate."
                        self.progressMessage = "Plan preview still working: \(self.lastEngineMessage)"
                    } else {
                        self.status = "\(label) may be stuck. You can cancel and copy the debug report if it fails."
                        self.progressMessage = "Possibly stuck at: \(self.lastEngineMessage)"
                    }
                } else if idleSeconds >= 20 {
                    self.progressMessage = "Still working: \(self.lastEngineMessage)"
                }
                self.updateTimingEstimate()
            }
        }
    }

    private func stopActivityMonitorIfIdle() {
        guard !isWorking && !isBuildingPreview && !isPlanningPreview else { return }
        activityMonitorTask?.cancel()
        activityMonitorTask = nil
    }
}
