import AppKit
import Foundation
import SwiftUI

@MainActor
final class StudioStore: ObservableObject {
    @Published var mode: PaletteMode = .official
    @Published var paletteSource: PaletteSource = .inventory
    @Published var realSlots: RealSlotSelection = .auto
    @Published var inspection: ProjectInspection?
    @Published var result: ConversionResult?
    @Published var inventory: InventorySnapshot?
    @Published var previewImage: NSImage?
    @Published var previewMeshURL: URL?
    @Published var outputPreviewMeshURL: URL?
    @Published var selectedFile: URL?
    @Published var referenceURL: URL?
    @Published var customPaletteURL: URL?
    @Published var status = "Drop a Bambu 3MF to begin."
    @Published var errorMessage: String?
    @Published var isWorking = false
    @Published var isBuildingPreview = false
    @Published var isRefreshingInventory = false
    @Published var showingImporter = false
    @Published var showingReferenceImporter = false
    @Published var showingCustomPaletteImporter = false
    @Published var progress = 0.0
    @Published var progressMessage = "Waiting for a model."
    @AppStorage("autoOpenValidatedOutput") var autoOpenValidatedOutput = true

    private let service = ConverterService()
    private var inspectionID = UUID()

    init() {
        refreshInventory()
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
        if url.pathExtension.lowercased() != "3mf" {
            acceptReference(url: url)
            return
        }
        selectedFile = url
        let currentInspectionID = UUID()
        inspectionID = currentInspectionID
        result = nil
        previewImage = nil
        previewMeshURL = nil
        outputPreviewMeshURL = nil
        isBuildingPreview = false
        progress = 0
        progressMessage = "Reading model metadata."
        errorMessage = nil
        status = "Reading project preview and material slots..."
        isWorking = true
        let previewURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-\(UUID().uuidString).png")
        let previewMeshURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-\(UUID().uuidString).obj")

        Task {
            do {
                let project = try await service.inspect(file: url, thumbnailURL: previewURL)
                guard inspectionID == currentInspectionID else { return }
                inspection = project
                previewImage = project.thumbnail.flatMap { NSImage(contentsOfFile: $0) }
                status = "\(project.sourceSlots) source filaments ready for conversion."
                buildInteractivePreview(for: url, outputURL: previewMeshURL, inspectionID: currentInspectionID)
            } catch {
                guard inspectionID == currentInspectionID else { return }
                errorMessage = error.localizedDescription
                status = "Could not open that project."
            }
            if inspectionID == currentInspectionID {
                isWorking = false
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

    private func buildInteractivePreview(for file: URL, outputURL: URL, inspectionID: UUID) {
        isBuildingPreview = true
        Task {
            do {
                let project = try await service.previewMesh(file: file, outputURL: outputURL)
                guard self.inspectionID == inspectionID else { return }
                previewMeshURL = project.previewMesh.map(URL.init(fileURLWithPath:))
                if !isWorking {
                    status = "\(project.sourceSlots) source filaments ready. Drag the preview to inspect it."
                }
            } catch {
                guard self.inspectionID == inspectionID else { return }
                if !isWorking {
                    status = "Ready for conversion. Interactive preview could not be generated."
                }
            }
            if self.inspectionID == inspectionID {
                isBuildingPreview = false
            }
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
        Task {
            do {
                let converted = try await service.convert(
                    file: file,
                    mode: mode,
                    paletteSource: paletteSource,
                    realSlots: realSlots,
                    reference: referenceURL,
                    customPalette: customPaletteURL,
                    outputDirectory: file.deletingLastPathComponent(),
                    progress: { [weak self] value, message in
                        Task { @MainActor in
                            self?.progress = value
                            self?.progressMessage = message
                        }
                    }
                )
                result = converted
                inventory = converted.inventory
                progress = 1
                progressMessage = "Validated output is ready."
                status = "Validated: \(converted.realSlots) physical and \(converted.outputSlots - converted.realSlots) mixed slots."
                buildOutputPreview(for: converted.output)
                if autoOpenValidatedOutput {
                    openOutput()
                }
            } catch {
                errorMessage = error.localizedDescription
                status = "Conversion failed."
                progressMessage = "Conversion failed."
            }
            isWorking = false
        }
    }

    private func buildOutputPreview(for path: String) {
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-Predicted-\(UUID().uuidString).obj")
        Task {
            do {
                let project = try await service.previewMesh(
                    file: URL(fileURLWithPath: path),
                    outputURL: outputURL
                )
                outputPreviewMeshURL = project.previewMesh.map(URL.init(fileURLWithPath:))
            } catch {
                outputPreviewMeshURL = nil
            }
        }
    }

    func revealOutput() {
        guard let path = result?.output else { return }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }

    func openOutput() {
        guard let path = result?.output else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }
}
