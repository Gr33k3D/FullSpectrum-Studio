import AppKit
import SwiftUI

struct ModelPreviewCard: View {
    @EnvironmentObject private var store: StudioStore
    @State private var isTargeted = false
    @State private var cameraResetToken = 0
    @State private var isFullScreen = false
    @AppStorage("wastePreviewDisplayScale") private var wastePreviewDisplayScale = 0.7
    var compact = false

    private var activeMeshURL: URL? {
        switch store.previewMode {
        case .plateImage:
            return nil
        case .predicted, .validation:
            return store.outputPreviewMeshURL
        case .colorLoss:
            return store.heatmapMeshURL
        case .anchorInfluence:
            return store.anchorInfluenceMeshURL
        case .wireframe:
            return store.outputPreviewMeshURL ?? store.previewMeshURL
        case .original:
            return store.previewMeshURL
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("PREVIEW")
                    .font(.caption.weight(.bold))
                    .tracking(1.2)
                    .foregroundStyle(Color.studioTertiaryText)
                Spacer()
                if let project = store.inspection {
                    Text("\(project.sourceSlots) original slots")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Color.studioAccent)
                }
                if store.inspection != nil {
                    Picker("Preview", selection: $store.previewMode) {
                        ForEach(availablePreviewModes) { mode in
                            Text(mode.rawValue).tag(mode)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(width: 160)
                }
            }

            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.black.opacity(0.28))
                    .overlay {
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(isTargeted ? Color.studioAccent : Color.studioBorder, lineWidth: isTargeted ? 2 : 1)
                    }

                if let meshURL = activeMeshURL {
                    InteractiveModelView(
                        meshURL: meshURL,
                        resetToken: cameraResetToken,
                        wireframe: store.previewMode == .wireframe,
                        performance: store.viewerPerformance,
                        displayScale: previewDisplayScale
                    )
                        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                        .overlay(alignment: .top) {
                            ViewerToolbar(
                                isFullScreen: isFullScreen,
                                reset: { cameraResetToken += 1 },
                                toggleFullScreen: {
                                    NSApp.keyWindow?.toggleFullScreen(nil)
                                    isFullScreen.toggle()
                                }
                            )
                            .frame(maxWidth: .infinity, alignment: .center)
                            .padding(.horizontal, 12)
                            .padding(.top, 8)
                        }
                } else if store.previewMode == .plateImage, let image = store.previewImage {
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
                                    .background(.black.opacity(0.5), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
                                    .padding(12)
                            }
                        }
                } else if store.inspection != nil {
                    PreviewModePlaceholder(mode: store.previewMode)
                } else {
                    EmptyDropPrompt(isTargeted: isTargeted)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
                        .offset(y: compact ? -28 : -54)
                        .overlay(alignment: .bottom) {
                            if store.isBuildingPreview {
                                Label(store.progressMessage, systemImage: "hourglass")
                                    .font(.caption)
                                    .foregroundStyle(.cyan.opacity(0.9))
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(.black.opacity(0.5), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
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
                        .background(.black.opacity(0.58), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
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
                    .foregroundStyle(Color.studioWarning)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if store.isBuildingPreview || store.isPlanningPreview || store.isWorking {
                Label(store.timingMessage, systemImage: "clock")
                    .font(.caption)
                    .foregroundStyle(Color.studioAccent)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let reference = store.referenceURL {
                Label("Visual target: \(reference.lastPathComponent)", systemImage: "scope")
                    .font(.caption)
                    .foregroundStyle(Color.studioAccent)
                    .lineLimit(1)
            }
            if store.previewMode == .validation, let validation = store.result?.colorValidation {
                Label(
                    "App prediction vs Bambu reconstructed: maximum Delta E \(String(format: "%.2f", validation.maximumDeltaE))",
                    systemImage: validation.verified ? "checkmark.shield" : "exclamationmark.triangle"
                )
                .font(.caption)
                .foregroundStyle(validation.verified ? Color.studioSuccess : Color.studioWarning)
            }
            HStack(spacing: 12) {
                if store.inspection?.metrics == nil {
                    Spacer(minLength: 0)
                }
                renderControlGroup
                if let metrics = store.inspection?.metrics {
                    Spacer()
                    Text("\(metrics.triangleCount.formatted()) polygons | \(metrics.vertexCount.formatted()) vertices | \(ByteCountFormatter.string(fromByteCount: Int64(metrics.previewMemoryEstimateBytes), countStyle: .memory)) preview memory | ~\(String(format: "%.1f", metrics.previewBuildEstimateSeconds))s build")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(Color.studioTertiaryText)
                } else {
                    Spacer(minLength: 0)
                }
            }
            .font(.caption)
            .foregroundStyle(.white.opacity(0.64))
        }
        .padding(17)
        .background(CardSurface())
        .onChange(of: store.result?.output) { _, newOutput in
            if newOutput != nil {
                store.previewMode = store.outputPreviewMeshURL == nil ? .original : .predicted
            }
        }
        .onChange(of: previewAvailabilityKey) { _, _ in
            ensureAvailablePreviewMode()
        }
    }

    private var renderControlGroup: some View {
        HStack(spacing: 12) {
            Picker("Render", selection: $store.viewerPerformance) {
                ForEach(ViewerPerformance.allCases) { option in Text(option.rawValue).tag(option) }
            }
            .pickerStyle(.menu)
            if showsWasteScaleControl {
                Picker("Waste preview size", selection: $wastePreviewDisplayScale) {
                    Text("100").tag(1.0)
                    Text("75").tag(0.75)
                    Text("50").tag(0.5)
                    Text("35").tag(0.35)
                    }
                .pickerStyle(.segmented)
                .frame(width: 210)
                .help("Visual-only display scale for color-loss and anchor-influence previews. The generated 3MF is unchanged.")
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

    private var showsWasteScaleControl: Bool {
        store.previewMode == .colorLoss || store.previewMode == .anchorInfluence
    }

    private var previewDisplayScale: Double {
        showsWasteScaleControl ? wastePreviewDisplayScale : 1.0
    }

    private var availablePreviewModes: [PreviewMode] {
        var modes: [PreviewMode] = []
        if store.previewImage != nil {
            modes.append(.plateImage)
        }
        if store.previewMeshURL != nil {
            modes.append(.original)
        }
        if store.outputPreviewMeshURL != nil {
            modes.append(.predicted)
            modes.append(.validation)
        }
        if store.heatmapMeshURL != nil {
            modes.append(.colorLoss)
        }
        if store.anchorInfluenceMeshURL != nil {
            modes.append(.anchorInfluence)
        }
        if store.previewMeshURL != nil || store.outputPreviewMeshURL != nil {
            modes.append(.wireframe)
        }
        return modes.isEmpty ? [.original] : modes
    }

    private var previewAvailabilityKey: String {
        availablePreviewModes.map(\.rawValue).joined(separator: "|")
    }

    private func ensureAvailablePreviewMode() {
        guard !availablePreviewModes.contains(store.previewMode) else { return }
        if store.previewMeshURL != nil {
            store.previewMode = .original
        } else if let first = availablePreviewModes.first {
            store.previewMode = first
        }
    }
}

private struct ViewerToolbar: View {
    let isFullScreen: Bool
    let reset: () -> Void
    let toggleFullScreen: () -> Void

    var body: some View {
        HStack(alignment: .center, spacing: 8) {
            Button(action: reset) {
                Image(systemName: "viewfinder")
                    .frame(width: 26, height: 26)
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.studioAccent)
            .help("Reset camera")
            Button(action: toggleFullScreen) {
                Image(systemName: isFullScreen ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right")
                    .frame(width: 26, height: 26)
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.studioAccent)
            .help("Toggle fullscreen viewer window")
        }
        .frame(minHeight: 34, alignment: .center)
        .padding(.horizontal, 8)
        .background(.black.opacity(0.58), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 6, style: .continuous).stroke(Color.studioBorder, lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.22), radius: 12, y: 5)
    }
}

private struct EmptyDropPrompt: View {
    let isTargeted: Bool

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: isTargeted ? "square.and.arrow.down.fill" : "cube.transparent")
                .font(.system(size: 45, weight: .light))
                .foregroundStyle(isTargeted ? Color.studioAccent : Color.studioTertiaryText)
            Text(isTargeted ? "Release to load file" : "Drop a painted .3mf, textured .obj or .glb here")
                .font(.title3.weight(.medium))
                .foregroundStyle(Color.studioPrimaryText)
            Text("Images can also be added as visual references")
                .font(.callout)
                .foregroundStyle(Color.studioTertiaryText)
        }
    }
}

private struct PreviewModePlaceholder: View {
    let mode: PreviewMode

    var body: some View {
        VStack(spacing: 13) {
            Image(systemName: "cube.transparent")
                .font(.system(size: 42, weight: .light))
                .foregroundStyle(.white.opacity(0.34))
            Text(mode.rawValue)
                .font(.title3.weight(.medium))
                .foregroundStyle(.white.opacity(0.76))
            Text("Waiting for preview asset")
                .font(.callout)
                .foregroundStyle(.white.opacity(0.42))
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
        RoundedRectangle(cornerRadius: 8, style: .continuous)
            .fill(Color.studioPanel)
            .overlay {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(Color.studioBorder, lineWidth: 1)
            }
    }
}
