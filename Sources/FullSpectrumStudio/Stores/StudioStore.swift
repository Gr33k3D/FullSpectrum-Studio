import AppKit
import Foundation
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class StudioStore: ObservableObject {
    @Published var mode: PaletteMode = .official
    @Published var paletteSource: PaletteSource = .inventory
    @Published var realSlots: RealSlotSelection = .auto
    @Published var mixPrediction: MixPrediction = .perceptual
    @Published var qualityBias = 60.0
    @Published var previewMode: PreviewMode = .original
    @Published var viewerPerformance: ViewerPerformance = .balanced
    @Published var inventorySearch = ""
    @Published var inspection: ProjectInspection?
    @Published var result: ConversionResult?
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
    @Published var isBuildingPreview = false
    @Published var isRefreshingInventory = false
    @Published var progress = 0.0
    @Published var progressMessage = "Waiting for a model."
    @AppStorage("autoOpenValidatedOutput") var autoOpenValidatedOutput = true
    @AppStorage("restoreLastSession") var restoreLastSession = false
    @AppStorage("lastProjectPath") private var lastProjectPath = ""

    private let service = ConverterService()
    private var inspectionID = UUID()
    private var inspectionTask: Task<Void, Never>?
    private var previewTask: Task<Void, Never>?
    private var conversionID = UUID()
    private var conversionTask: Task<Void, Never>?
    private var outputPreviewTask: Task<Void, Never>?
    private var retainedSourceURL: URL?
    private var retainedSourceAccess = false
    private let immediateImportedPreviewByteLimit = 48 * 1024 * 1024

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
            } catch {
                errorMessage = error.localizedDescription
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

    func chooseCustomPaletteFile() {
        chooseFile(
            title: "Choose Filament Library",
            message: "Choose a local JSON file describing custom filament colors.",
            extensions: ["json"],
            choosingStatus: "Choose a custom filament JSON library."
        ) { [weak self] url in
            self?.acceptCustomPalette(url: url)
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
        retainSelectedSourceAccess(to: url)
        selectedFile = url
        lastProjectPath = url.path
        let currentInspectionID = UUID()
        inspectionID = currentInspectionID
        inspection = nil
        result = nil
        previewImage = nil
        previewMeshURL = nil
        outputPreviewMeshURL = nil
        heatmapMeshURL = nil
        anchorInfluenceMeshURL = nil
        previewMode = .original
        isBuildingPreview = true
        progress = 0
        progressMessage = "Reading model metadata."
        errorMessage = nil
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
                    errorMessage = error.localizedDescription
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
                            self?.progress = value
                            self?.progressMessage = message
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
                status = project.previewNotice ?? "\(project.sourceSlots) source filaments ready for conversion."
            } catch is CancellationError {
                return
            } catch {
                guard inspectionID == currentInspectionID else { return }
                errorMessage = error.localizedDescription
                status = "Could not open that project."
            }
            if inspectionID == currentInspectionID {
                isBuildingPreview = false
                progress = 0
                progressMessage = "Ready for conversion."
                previewTask = nil
            }
        }
    }

    func acceptReference(url: URL) {
        let supported = ["obj", "glb", "png", "jpg", "jpeg", "bmp", "tif", "tiff"]
        guard supported.contains(url.pathExtension.lowercased()) else {
            errorMessage = "Reference mode accepts OBJ, GLB or a texture image."
            return
        }
        referenceURL = url
        result = nil
        status = "Reference selected: \(url.lastPathComponent). Load or convert a 3MF to score it."
    }

    func acceptCustomPalette(url: URL) {
        guard url.pathExtension.lowercased() == "json" else {
            errorMessage = "Custom filament libraries must be JSON files."
            return
        }
        customPaletteURL = url
        paletteSource = .custom
    }

    func acceptTextureOverride(url: URL) {
        guard ["png", "jpg", "jpeg"].contains(url.pathExtension.lowercased()) else {
            errorMessage = "OBJ import textures must be PNG or JPEG files."
            return
        }
        textureOverrideURL = url
        if let selectedFile, selectedFile.pathExtension.lowercased() == "obj" {
            accept(url: selectedFile)
        }
    }

    func convert() {
        guard let file = selectedFile else {
            chooseSourceFile()
            return
        }
        if paletteSource == .custom && customPaletteURL == nil {
            chooseCustomPaletteFile()
            return
        }
        isWorking = true
        errorMessage = nil
        progress = 0
        progressMessage = "Starting conversion."
        status = "Converting painted facets and validating the output..."
        inspectionTask?.cancel()
        previewTask?.cancel()
        outputPreviewTask?.cancel()
        isBuildingPreview = false
        conversionTask?.cancel()
        let currentConversionID = UUID()
        conversionID = currentConversionID
        let capturedReference = referenceURL
        let capturedPalette = customPaletteURL
        let capturedTexture = textureOverrideURL
        let capturedPrediction = mixPrediction
        conversionTask = Task {
            let temporaryAccess = beginTemporaryAccess(to: [capturedReference, capturedPalette, capturedTexture])
            defer { endTemporaryAccess(temporaryAccess) }
            do {
                let converted = try await service.convert(
                    file: file,
                    mode: mode,
                    paletteSource: paletteSource,
                    realSlots: realSlots,
                    reference: capturedReference,
                    customPalette: capturedPalette,
                    textureOverride: capturedTexture,
                    qualityBias: Int(qualityBias),
                    mixPrediction: capturedPrediction,
                    outputDirectory: file.deletingLastPathComponent(),
                    progress: { [weak self] value, message in
                        Task { @MainActor in
                            guard self?.conversionID == currentConversionID else { return }
                            self?.progress = value
                            self?.progressMessage = message
                        }
                    }
                )
                guard conversionID == currentConversionID else { return }
                result = converted
                inventory = converted.inventory
                heatmapMeshURL = converted.analysisAssets?.heatmapMesh.map(URL.init(fileURLWithPath:))
                anchorInfluenceMeshURL = converted.analysisAssets?.anchorInfluenceMesh.map(URL.init(fileURLWithPath:))
                progress = 1
                progressMessage = "Validated output is ready."
                status = "Validated: \(converted.realSlots) physical and \(converted.outputSlots - converted.realSlots) mixed slots."
                buildOutputPreview(for: converted.output, conversionID: currentConversionID, mixPrediction: capturedPrediction)
                if autoOpenValidatedOutput {
                    openOutput()
                }
            } catch is CancellationError {
                guard conversionID == currentConversionID else { return }
                status = "Conversion cancelled."
                progressMessage = "Cancelled."
            } catch {
                guard conversionID == currentConversionID else { return }
                errorMessage = error.localizedDescription
                status = "Conversion failed."
                progressMessage = "Conversion failed."
            }
            if conversionID == currentConversionID {
                isWorking = false
                conversionTask = nil
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
        inspectionTask = nil
        previewTask = nil
        outputPreviewTask = nil
        conversionTask = nil
        isWorking = false
        isBuildingPreview = false
        status = "Conversion cancelled."
        progressMessage = "Cancelled."
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
        status = inspection == nil ? "Preview stopped. Choose a source to try again." : "Ready for conversion. Interactive preview stopped."
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
            errorMessage = "The validated output file could not be found."
            return
        }
        NSWorkspace.shared.activateFileViewerSelecting([outputURL])
    }

    func openOutput() {
        guard let path = result?.output else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }
}
