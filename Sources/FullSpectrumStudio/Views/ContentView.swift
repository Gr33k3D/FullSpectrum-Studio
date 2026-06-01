import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var store: StudioStore
    @State private var sidebarVisible = true
    @State private var activityExpanded = false

    var body: some View {
        GeometryReader { geometry in
            let compactHeight = geometry.size.height < 900
            let compactHeader = geometry.size.width < 1120

            ZStack {
                StudioBackground()

                VStack(spacing: 16) {
                    HeaderView(sidebarVisible: $sidebarVisible, compact: compactHeader)

                    if geometry.size.width >= 980 {
                        HStack(alignment: .top, spacing: 16) {
                            if compactHeight {
                                ScrollView {
                                    primaryWorkspace(compactHeight: true, availableHeight: geometry.size.height)
                                }
                                .scrollIndicators(.visible)
                            } else {
                                primaryWorkspace(compactHeight: false, availableHeight: geometry.size.height)
                            }

                            if sidebarVisible {
                                ScrollView {
                                    VStack(spacing: 14) {
                                        ConversionControlsCard()
                                        InventoryCard()
                                        PaletteResultsCard()
                                            .frame(minHeight: 520)
                                    }
                                }
                                .scrollIndicators(.visible)
                                .frame(width: min(440, max(360, geometry.size.width * 0.35)))
                                .frame(maxHeight: geometry.size.height - 92)
                                .transition(.move(edge: .trailing).combined(with: .opacity))
                            }
                        }
                    } else {
                        ScrollView {
                            VStack(spacing: 14) {
                                ModelPreviewCard(compact: true)
                                ActivityPanel(isExpanded: $activityExpanded)
                                if sidebarVisible {
                                    ConversionControlsCard()
                                    InventoryCard()
                                    PaletteResultsCard().frame(minHeight: 520)
                                }
                            }
                        }
                    }
                }
                .animation(.easeOut(duration: 0.18), value: sidebarVisible)
                .padding(24)

                VersionCornerBadge()
                    .padding(18)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing)
                    .allowsHitTesting(false)
            }
        }
        .onOpenURL { url in
            store.accept(url: url)
        }
        .preferredColorScheme(.dark)
        .alert("FullSpectrum Studio", isPresented: Binding(
            get: { store.errorMessage != nil },
            set: { if !$0 { store.clearError() } }
        )) {
            if store.errorReport != nil {
                Button("Copy Error Report") { store.copyErrorReport() }
            }
            if store.errorReport?.logURL != nil {
                Button("Open Debug Log") { store.openErrorLog() }
            }
            Button("OK", role: .cancel) { store.clearError() }
        } message: {
            Text(store.errorReport?.message ?? store.errorMessage ?? "")
        }
    }

    @ViewBuilder
    private func primaryWorkspace(compactHeight: Bool, availableHeight: CGFloat) -> some View {
        VStack(spacing: 12) {
            ModelPreviewCard(compact: compactHeight)
                .frame(minHeight: compactHeight ? 470 : max(560, availableHeight - 215))
            ActivityPanel(isExpanded: $activityExpanded)
        }
        .layoutPriority(1)
    }
}

private struct VersionCornerBadge: View {
    private var versionText: String {
        let info = Bundle.main.infoDictionary ?? [:]
        let version = info["CFBundleShortVersionString"] as? String ?? "dev"
        let build = info["CFBundleVersion"] as? String
        let infoString = (info["CFBundleGetInfoString"] as? String ?? "").lowercased()
        let suffix = infoString.contains("local") ? " local" : ""
        if let build, !build.isEmpty {
            return "v\(version) (\(build))\(suffix)"
        }
        return "v\(version)\(suffix)"
    }

    var body: some View {
        Text(versionText)
            .font(.caption2.monospacedDigit().weight(.semibold))
            .foregroundStyle(.white.opacity(0.58))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(.black.opacity(0.34), in: Capsule())
            .overlay {
                Capsule().stroke(.white.opacity(0.08), lineWidth: 1)
            }
            .shadow(color: .black.opacity(0.18), radius: 8, y: 3)
            .accessibilityLabel("Version \(versionText)")
    }
}

private struct ActivityPanel: View {
    @EnvironmentObject private var store: StudioStore
    @Binding var isExpanded: Bool

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 7) {
                Label(store.timingMessage, systemImage: "clock")
                    .foregroundStyle(.cyan.opacity(0.76))
                    .textSelection(.enabled)
                ForEach(Array(store.activityMessages.reversed().enumerated()), id: \.offset) { _, message in
                    Text(message)
                        .textSelection(.enabled)
                }
                if let notice = store.inspection?.previewNotice {
                    Text(notice)
                }
                if let preview = store.planPreview {
                    Text("Plan preview: \(preview.realSlots) physical + \(preview.outputSlots - preview.realSlots) mixed slots. No output file written.")
                        .foregroundStyle(.cyan.opacity(0.74))
                }
                ForEach(store.result?.warnings ?? [], id: \.self) { warning in
                    Text(warning).foregroundStyle(.orange.opacity(0.9))
                }
            }
            .font(.caption)
            .foregroundStyle(.white.opacity(0.64))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 8)
        } label: {
            HStack {
                Label("Activity and Validation Log", systemImage: "text.badge.checkmark")
                Spacer()
                Text(store.status)
                    .lineLimit(2)
                    .multilineTextAlignment(.trailing)
                    .foregroundStyle(.white.opacity(0.48))
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(.cyan.opacity(0.82))
        }
        .padding(12)
        .background(CardSurface())
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
    @Binding var sidebarVisible: Bool
    let compact: Bool

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
                    .font(.system(size: compact ? 22 : 26, weight: .semibold, design: .rounded))
                    .foregroundStyle(.white)
                if !compact {
                    Text("Local painted-project palette reduction and validation")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.56))
                }
            }

            Spacer()

            StatusPill(
                title: store.result == nil ? ((store.isWorking || store.isPlanningPreview || store.isBuildingPreview) ? "Processing" : "Ready") : "Validated",
                icon: store.result == nil ? ((store.isWorking || store.isPlanningPreview || store.isBuildingPreview) ? "sparkles" : "circle.dotted") : "checkmark.seal.fill",
                tint: store.result == nil ? .cyan : .green
            )

            if store.isWorking || store.isPlanningPreview || store.isBuildingPreview {
                Button {
                    store.cancelActiveOperation()
                } label: {
                    if compact {
                        Image(systemName: "xmark.circle.fill")
                    } else {
                        Label(store.isBuildingPreview ? "Stop Preview" : "Cancel", systemImage: "xmark.circle.fill")
                    }
                }
                .buttonStyle(StudioButtonStyle(prominent: false, tint: .red))
                .help(store.isBuildingPreview ? "Stop the optional preview build" : "Terminate the active Python planner process")
            }

            Button {
                store.chooseSourceFile()
            } label: {
                if compact {
                    Image(systemName: "plus")
                } else {
                    Label("Open Source", systemImage: "plus")
                }
            }
            .buttonStyle(StudioButtonStyle(prominent: false))
            .help("Open a painted source project")

            Button {
                store.chooseReferenceFile()
            } label: {
                if compact {
                    Image(systemName: "photo.on.rectangle")
                } else {
                    Label("Reference", systemImage: "photo.on.rectangle")
                }
            }
            .buttonStyle(StudioButtonStyle(prominent: false))
            .help("Choose a visual reference")

            Button {
                sidebarVisible.toggle()
            } label: {
                if compact {
                    Image(systemName: "sidebar.right")
                } else {
                    Label(sidebarVisible ? "Hide Tools" : "Show Tools", systemImage: "sidebar.right")
                }
            }
            .buttonStyle(StudioButtonStyle(prominent: false))
            .help("Toggle palette and validation controls")
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
    var tint: Color = .cyan

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.callout.weight(.semibold))
            .foregroundStyle(.white.opacity(configuration.isPressed ? 0.82 : 1.0))
            .padding(.horizontal, 17)
            .padding(.vertical, 10)
            .background {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .fill(
                        prominent
                        ? AnyShapeStyle(LinearGradient(colors: [tint.opacity(0.92), .blue.opacity(0.78)], startPoint: .topLeading, endPoint: .bottomTrailing))
                        : AnyShapeStyle(Color.white.opacity(configuration.isPressed ? 0.12 : 0.10))
                    )
            }
            .overlay {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .stroke((prominent ? Color.white : tint).opacity(prominent ? 0.12 : 0.28), lineWidth: 1)
            }
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
    }
}
