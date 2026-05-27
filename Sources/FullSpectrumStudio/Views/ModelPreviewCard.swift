import AppKit
import SwiftUI

struct ModelPreviewCard: View {
    @EnvironmentObject private var store: StudioStore
    @State private var isTargeted = false
    @State private var cameraResetToken = 0
    @State private var isFullScreen = false
    var compact = false

    private var activeMeshURL: URL? {
        switch store.previewMode {
        case .plateImage:
            return store.previewImage == nil ? store.previewMeshURL : nil
        case .predicted, .validation:
            return store.outputPreviewMeshURL ?? store.previewMeshURL
        case .colorLoss:
            return store.heatmapMeshURL ?? store.outputPreviewMeshURL ?? store.previewMeshURL
        case .anchorInfluence:
            return store.anchorInfluenceMeshURL ?? store.outputPreviewMeshURL ?? store.previewMeshURL
        case .wireframe:
            return store.outputPreviewMeshURL ?? store.previewMeshURL
        case .original:
            return store.previewMeshURL
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("MODEL PREVIEW")
                    .font(.caption.weight(.bold))
                    .tracking(1.2)
                    .foregroundStyle(.white.opacity(0.5))
                Spacer()
                if let project = store.inspection {
                    Text("\(project.sourceSlots) original slots")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.cyan.opacity(0.88))
                }
                if store.inspection != nil {
                    Picker("Preview", selection: $store.previewMode) {
                        ForEach(PreviewMode.allCases) { mode in
                            Text(mode.rawValue).tag(mode)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(width: 160)
                }
            }

            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(Color.black.opacity(0.24))
                    .overlay {
                        RoundedRectangle(cornerRadius: 20, style: .continuous)
                            .stroke(isTargeted ? Color.cyan.opacity(0.8) : .white.opacity(0.08), lineWidth: isTargeted ? 2 : 1)
                    }

                if let meshURL = activeMeshURL {
                    InteractiveModelView(
                        meshURL: meshURL,
                        resetToken: cameraResetToken,
                        wireframe: store.previewMode == .wireframe,
                        performance: store.viewerPerformance
                    )
                        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                        .overlay(alignment: .topTrailing) {
                            HStack(spacing: 8) {
                                Text("Drag to orbit  |  Scroll to zoom")
                                    .font(.caption)
                                    .foregroundStyle(.white.opacity(0.66))
                                Button {
                                    cameraResetToken += 1
                                } label: {
                                    Image(systemName: "viewfinder")
                                }
                                .buttonStyle(.plain)
                                .foregroundStyle(.cyan.opacity(0.9))
                                .help("Reset camera")
                                Button {
                                    NSApp.keyWindow?.toggleFullScreen(nil)
                                    isFullScreen.toggle()
                                } label: {
                                    Image(systemName: isFullScreen ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right")
                                }
                                .buttonStyle(.plain)
                                .foregroundStyle(.cyan.opacity(0.9))
                                .help("Toggle fullscreen viewer window")
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(.black.opacity(0.42), in: Capsule())
                            .padding(12)
                        }
                } else if let image = store.previewImage {
                    Image(nsImage: image)
                        .resizable()
                        .scaledToFit()
                        .padding(16)
                        .shadow(color: .cyan.opacity(0.14), radius: 30, y: 8)
                        .overlay(alignment: .topTrailing) {
                            if store.isBuildingPreview {
                                Label("Building 3D preview", systemImage: "cube.transparent")
                                    .font(.caption)
                                    .foregroundStyle(.cyan.opacity(0.9))
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(.black.opacity(0.42), in: Capsule())
                                    .padding(12)
                            }
                        }
                } else {
                    EmptyDropPrompt(isTargeted: isTargeted)
                        .overlay(alignment: .bottom) {
                            if store.isBuildingPreview {
                                Label(store.progressMessage, systemImage: "hourglass")
                                    .font(.caption)
                                    .foregroundStyle(.cyan.opacity(0.9))
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(.black.opacity(0.42), in: Capsule())
                                    .padding(12)
                            }
                        }
                }

                if let project = store.inspection {
                    VStack(spacing: 0) {
                        Spacer()
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(project.filename)
                                    .font(.callout.weight(.medium))
                                    .foregroundStyle(.white.opacity(0.9))
                                    .lineLimit(1)
                                Text(store.previewMeshURL == nil ? "Bambu 3MF plate render" :
                                        previewCaption)
                                    .font(.caption)
                                    .foregroundStyle(.white.opacity(0.5))
                            }
                            Spacer()
                            Image(systemName: "cube.fill")
                                .foregroundStyle(.cyan.opacity(0.7))
                        }
                        .padding(14)
                        .background(.black.opacity(0.4), in: RoundedRectangle(cornerRadius: 15, style: .continuous))
                        .padding(12)
                    }
                }
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: compact ? 400 : 520, idealHeight: compact ? 500 : 680, maxHeight: .infinity)
            .dropDestination(for: URL.self) { urls, _ in
                guard let url = urls.first else { return false }
                store.accept(url: url)
                return true
            } isTargeted: { targeted in
                withAnimation(.easeOut(duration: 0.18)) {
                    isTargeted = targeted
                }
            }

            if let colors = store.inspection?.sourceColors {
                SourcePaletteStrip(colors: colors)
            } else {
                Text("The original model stays geometrically untouched; only material assignments are rewritten.")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.48))
            }
            if let notice = store.inspection?.previewNotice {
                Label(notice, systemImage: "memorychip")
                    .font(.caption)
                    .foregroundStyle(.orange.opacity(0.82))
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let reference = store.referenceURL {
                Label("Visual target: \(reference.lastPathComponent)", systemImage: "scope")
                    .font(.caption)
                    .foregroundStyle(.cyan.opacity(0.72))
                    .lineLimit(1)
            }
            if store.previewMode == .validation, let validation = store.result?.colorValidation {
                Label(
                    "App prediction vs Bambu reconstructed: maximum Delta E \(String(format: "%.2f", validation.maximumDeltaE))",
                    systemImage: validation.verified ? "checkmark.shield" : "exclamationmark.triangle"
                )
                .font(.caption)
                .foregroundStyle(validation.verified ? .green.opacity(0.86) : .orange.opacity(0.88))
            }
            HStack(spacing: 12) {
                Picker("Render", selection: $store.viewerPerformance) {
                    ForEach(ViewerPerformance.allCases) { option in Text(option.rawValue).tag(option) }
                }
                .pickerStyle(.menu)
                if let metrics = store.inspection?.metrics {
                    Spacer()
                    Text("\(metrics.triangleCount.formatted()) polygons | \(metrics.vertexCount.formatted()) vertices | \(ByteCountFormatter.string(fromByteCount: Int64(metrics.previewMemoryEstimateBytes), countStyle: .memory)) preview memory | ~\(String(format: "%.1f", metrics.previewBuildEstimateSeconds))s build")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.white.opacity(0.46))
                }
            }
            .font(.caption)
            .foregroundStyle(.white.opacity(0.64))
        }
        .padding(17)
        .background(CardSurface())
        .onChange(of: store.result?.output) { _, newOutput in
            if newOutput != nil {
                store.previewMode = .predicted
            }
        }
    }

    private var previewCaption: String {
        switch store.previewMode {
        case .plateImage:
            return "Original Bambu Studio plate render"
        case .original:
            return store.inspection?.`import` == nil
                ? "Original painted mesh preview"
                : "Imported painted approximation of source texture"
        case .predicted: return "Reduced palette with Bambu-reconstructed mixed colors"
        case .validation:
            return "Validation preview: app and Bambu reconstructed swatches match"
        case .colorLoss: return "Estimated color-loss heatmap: green low, red high"
        case .anchorInfluence: return "Dominant physical anchor influence"
        case .wireframe: return "Predicted palette wireframe"
        }
    }
}

private struct EmptyDropPrompt: View {
    let isTargeted: Bool

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: isTargeted ? "square.and.arrow.down.fill" : "cube.transparent")
                .font(.system(size: 45, weight: .light))
                .foregroundStyle(isTargeted ? .cyan : .white.opacity(0.38))
            Text(isTargeted ? "Release to load file" : "Drop a painted .3mf, textured .obj or .glb here")
                .font(.title3.weight(.medium))
                .foregroundStyle(.white.opacity(0.85))
            Text("Images can also be added as visual references")
                .font(.callout)
                .foregroundStyle(.white.opacity(0.45))
        }
    }
}

private struct SourcePaletteStrip: View {
    let colors: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("SOURCE PALETTE")
                .font(.caption2.weight(.bold))
                .tracking(0.9)
                .foregroundStyle(.white.opacity(0.42))
            HStack(spacing: 5) {
                ForEach(Array(colors.enumerated()), id: \.offset) { _, hex in
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .fill(Color(hex: hex))
                        .frame(height: 20)
                }
            }
        }
    }
}

struct CardSurface: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 20, style: .continuous)
            .fill(.white.opacity(0.045))
            .background {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(.ultraThinMaterial.opacity(0.2))
            }
            .overlay {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(.white.opacity(0.08), lineWidth: 1)
            }
    }
}
