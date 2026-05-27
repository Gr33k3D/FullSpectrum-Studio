import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject private var store: StudioStore

    private var sourceTypes: [UTType] {
        ["3mf", "obj", "glb"].map { UTType(filenameExtension: $0) ?? .data }
    }
    private var referenceTypes: [UTType] {
        ["obj", "glb", "png", "jpg", "jpeg", "bmp", "tif"].map { UTType(filenameExtension: $0) ?? .data }
    }
    private var textureTypes: [UTType] {
        ["png", "jpg", "jpeg"].map { UTType(filenameExtension: $0) ?? .image }
    }

    var body: some View {
        ZStack {
            StudioBackground()

            ScrollView {
                VStack(spacing: 20) {
                    HeaderView()

                    ViewThatFits(in: .horizontal) {
                        HStack(alignment: .top, spacing: 20) {
                            ModelPreviewCard()
                                .frame(minWidth: 400, idealWidth: 500, maxWidth: 570)

                            VStack(spacing: 16) {
                                ConversionControlsCard()
                                InventoryCard()
                                PaletteResultsCard()
                                    .frame(minHeight: 300)
                            }
                            .frame(minWidth: 400)
                        }

                        VStack(spacing: 16) {
                            ModelPreviewCard()
                                .frame(minHeight: 500)
                            ConversionControlsCard()
                            InventoryCard()
                            PaletteResultsCard()
                                .frame(minHeight: 390)
                        }
                    }
                }
                .padding(24)
            }
        }
        .fileImporter(
            isPresented: $store.showingImporter,
            allowedContentTypes: sourceTypes,
            allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first {
                store.accept(url: url)
            }
        }
        .fileImporter(
            isPresented: $store.showingReferenceImporter,
            allowedContentTypes: referenceTypes,
            allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first {
                store.acceptReference(url: url)
            }
        }
        .fileImporter(
            isPresented: $store.showingCustomPaletteImporter,
            allowedContentTypes: [.json],
            allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first {
                store.acceptCustomPalette(url: url)
            }
        }
        .fileImporter(
            isPresented: $store.showingTextureImporter,
            allowedContentTypes: textureTypes,
            allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first {
                store.acceptTextureOverride(url: url)
            }
        }
        .onOpenURL { url in
            store.accept(url: url)
        }
        .alert("FullSpectrum Studio", isPresented: Binding(
            get: { store.errorMessage != nil },
            set: { if !$0 { store.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { store.errorMessage = nil }
        } message: {
            Text(store.errorMessage ?? "")
        }
    }
}

private struct StudioBackground: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.035, green: 0.06, blue: 0.09),
                    Color(red: 0.025, green: 0.035, blue: 0.055),
                    Color(red: 0.02, green: 0.022, blue: 0.034)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            RadialGradient(
                colors: [
                    Color(red: 0.08, green: 0.56, blue: 0.64).opacity(0.16),
                    .clear
                ],
                center: .topTrailing,
                startRadius: 20,
                endRadius: 580
            )
        }
        .ignoresSafeArea()
    }
}

private struct HeaderView: View {
    @EnvironmentObject private var store: StudioStore

    var body: some View {
        HStack(spacing: 15) {
            ZStack {
                RoundedRectangle(cornerRadius: 15, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [Color.cyan.opacity(0.9), Color.indigo.opacity(0.75)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                Image(systemName: "cube.transparent.fill")
                    .font(.system(size: 23, weight: .medium))
                    .foregroundStyle(.white)
            }
            .frame(width: 48, height: 48)

            VStack(alignment: .leading, spacing: 3) {
                Text("FullSpectrum Studio")
                    .font(.system(size: 26, weight: .semibold, design: .rounded))
                    .foregroundStyle(.white)
                Text("Local painted-project palette reduction and validation")
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.56))
            }

            Spacer()

            StatusPill(
                title: store.result == nil ? ((store.isWorking || store.isBuildingPreview) ? "Processing" : "Ready") : "Validated",
                icon: store.result == nil ? ((store.isWorking || store.isBuildingPreview) ? "sparkles" : "circle.dotted") : "checkmark.seal.fill",
                tint: store.result == nil ? .cyan : .green
            )

            Button {
                store.showingImporter = true
            } label: {
                Label("Open Source", systemImage: "plus")
            }
            .buttonStyle(StudioButtonStyle(prominent: false))

            Button {
                store.showingReferenceImporter = true
            } label: {
                Label("Reference", systemImage: "photo.on.rectangle")
            }
            .buttonStyle(StudioButtonStyle(prominent: false))
        }
    }
}

private struct StatusPill: View {
    let title: String
    let icon: String
    let tint: Color

    var body: some View {
        Label(title, systemImage: icon)
            .font(.callout.weight(.medium))
            .foregroundStyle(tint)
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(tint.opacity(0.1), in: Capsule())
            .overlay {
                Capsule().stroke(tint.opacity(0.22), lineWidth: 1)
            }
    }
}

struct StudioButtonStyle: ButtonStyle {
    var prominent = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.callout.weight(.semibold))
            .foregroundStyle(.white.opacity(configuration.isPressed ? 0.75 : 0.96))
            .padding(.horizontal, 17)
            .padding(.vertical, 10)
            .background {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(
                        prominent
                        ? AnyShapeStyle(LinearGradient(colors: [.cyan.opacity(0.86), .blue.opacity(0.76)], startPoint: .topLeading, endPoint: .bottomTrailing))
                        : AnyShapeStyle(.white.opacity(configuration.isPressed ? 0.05 : 0.08))
                    )
            }
            .overlay {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .stroke(.white.opacity(prominent ? 0.08 : 0.1), lineWidth: 1)
            }
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
    }
}
