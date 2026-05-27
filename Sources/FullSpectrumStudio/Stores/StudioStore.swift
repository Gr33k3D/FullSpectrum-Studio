import AppKit
import Foundation
import SwiftUI

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
    @Published var showingImporter = false
    @Published var showingReferenceImporter = false
    @Published var showingTextureImporter = false
    @Published var showingCustomPaletteImporter = false
    @Published var progress = 0.0
    @Published var progressMessage = "Waiting for a model."
    @AppStorage("autoOpenValidatedOutput") var autoOpenValidatedOutput = true
    @AppStorage("restoreLastSession") var restoreLastSession = false
    @AppStorage("lastProjectPath") private var lastProjectPath = ""

    private let service = ConverterService()
    private var inspectionID = UUID()
    private var inspectionTask: Task<Void, Never>?
    private var conversionID = UUID()
    private var conversionTask: Task<Void, Never>?

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

    func accept(url: URL) {
        if !["3mf", "obj", "glb"].contains(url.pathExtension.lowercased()) {
            acceptReference(url: url)
            return
        }
        if selectedFile?.standardizedFileURL != url.standardizedFileURL || url.pathExtension.lowercased() != "obj" {
            textureOverrideURL = nil
        }
        inspectionTask?.cancel()
        conversionID = UUID()
        conversionTask?.cancel()
        selectedFile = url
        lastProjectPath = url.path
        let currentInspectionID = UUID()
        inspectionID = currentInspectionID
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
        status = ["obj", "glb"].contains(url.pathExtension.lowercased())
            ? "Building experimental painted preview from textured source..."
            : "Reading project preview and material slots..."
        isWorking = true
        let previewURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-\(UUID().uuidString).png")
        let previewMeshURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-\(UUID().uuidString).obj")

        inspectionTask = Task {
            do {
                let project = try await service.inspect(
                    file: url,
                    thumbnailURL: previewURL,
                    previewMeshURL: previewMeshURL,
                    textureOverride: textureOverrideURL,
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
                previewImage = project.thumbnail.flatMap { NSImage(contentsOfFile: $0) }
                self.previewMeshURL = project.previewMesh.map(URL.init(fileURLWithPath:))
                if let recommendation = project.metrics?.recommendedRenderMode,
                   let mode = ViewerPerformance(rawValue: recommendation) {
                    viewerPerformance = mode
                }
                status = "\(project.sourceSlots) source filaments ready for conversion."
            } catch is CancellationError {
                return
            } catch {
                guard inspectionID == currentInspectionID else { return }
                errorMessage = error.localizedDescription
                status = "Could not open that project."
            }
            if inspectionID == currentInspectionID {
                isWorking = false
                isBuildingPreview = false
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
            showingImporter = true
            return
        }
        if paletteSource == .custom && customPaletteURL == nil {
            showingCustomPaletteImporter = true
            return
        }
        isWorking = true
        errorMessage = nil
        progress = 0
        progressMessage = "Starting conversion."
        status = "Converting painted facets and validating the output..."
        inspectionTask?.cancel()
        conversionTask?.cancel()
        let currentConversionID = UUID()
        conversionID = currentConversionID
        conversionTask = Task {
            do {
                let converted = try await service.convert(
                    file: file,
                    mode: mode,
                    paletteSource: paletteSource,
                    realSlots: realSlots,
                    reference: referenceURL,
                    customPalette: customPaletteURL,
                    textureOverride: textureOverrideURL,
                    qualityBias: Int(qualityBias),
                    mixPrediction: mixPrediction,
                    outputDirectory: file.deletingLastPathComponent(),
                    progress: { [weak self] value, message in
                        Task { @MainActor in
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
                buildOutputPreview(for: converted.output)
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
        conversionID = UUID()
        conversionTask?.cancel()
        inspectionTask = nil
        conversionTask = nil
        isWorking = false
        isBuildingPreview = false
        status = "Conversion cancelled."
        progressMessage = "Cancelled."
    }

    private func buildOutputPreview(for path: String) {
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-Predicted-\(UUID().uuidString).obj")
        Task {
            do {
                let project = try await service.previewMesh(
                    file: URL(fileURLWithPath: path),
                    outputURL: outputURL,
                    mixPrediction: mixPrediction,
                    textureOverride: textureOverrideURL
                )
                outputPreviewMeshURL = project.previewMesh.map(URL.init(fileURLWithPath:))
            } catch {
                outputPreviewMeshURL = nil
            }
        }
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
