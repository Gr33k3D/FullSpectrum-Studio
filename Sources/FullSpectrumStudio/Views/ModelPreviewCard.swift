import SwiftUI

struct ModelPreviewCard: View {
    @EnvironmentObject private var store: StudioStore
    @State private var isTargeted = false
    @State private var cameraResetToken = 0
    @State private var showingPredicted = false

    private var activeMeshURL: URL? {
        if showingPredicted, let predicted = store.outputPreviewMeshURL {
            return predicted
        }
        return store.previewMeshURL
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
                if store.outputPreviewMeshURL != nil {
                    Picker("Preview", selection: $showingPredicted) {
                        Text("Original").tag(false)
                        Text("Predicted").tag(true)
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 178)
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
                    InteractiveModelView(meshURL: meshURL, resetToken: cameraResetToken)
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
                                        (showingPredicted ? "Predicted reduced-palette preview" : "Original painted mesh preview"))
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
            .frame(height: 475)
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
            if let reference = store.referenceURL {
                Label("Visual target: \(reference.lastPathComponent)", systemImage: "scope")
                    .font(.caption)
                    .foregroundStyle(.cyan.opacity(0.72))
                    .lineLimit(1)
            }
        }
        .padding(17)
        .background(CardSurface())
        .onChange(of: store.result?.output) { _, _ in
            showingPredicted = false
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
            Text(isTargeted ? "Release to load file" : "Drop a Bambu .3mf here")
                .font(.title3.weight(.medium))
                .foregroundStyle(.white.opacity(0.85))
            Text("You can also add an OBJ, GLB or texture reference")
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
