import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var store: StudioStore
    @State private var sidebarVisible = true
    @State private var activityExpanded = false
    @State private var inspectorSection: InspectorSection = .plan

    var body: some View {
        GeometryReader { geometry in
            let usesSplitLayout = geometry.size.width >= 980
            let compactHeader = geometry.size.width < 1160

            ZStack {
                StudioBackground()

                VStack(spacing: 0) {
                    HeaderView(sidebarVisible: $sidebarVisible, compact: compactHeader)
                        .padding(.horizontal, 20)
                        .padding(.vertical, 12)
                        .background(Color.studioChrome)

                    Divider().overlay(Color.studioBorder)

                    if usesSplitLayout {
                        HStack(spacing: 0) {
                            primaryWorkspace(availableHeight: geometry.size.height)
                                .padding(16)

                            if sidebarVisible {
                                Divider().overlay(Color.studioBorder)
                                InspectorPanel(selection: $inspectorSection)
                                    .frame(width: min(430, max(380, geometry.size.width * 0.33)))
                                    .transition(.move(edge: .trailing).combined(with: .opacity))
                            }
                        }
                    } else {
                        ScrollView {
                            VStack(spacing: 14) {
                                ModelPreviewCard(compact: true)
                                    .frame(minHeight: 480)
                                ActivityPanel(isExpanded: $activityExpanded)
                                if sidebarVisible {
                                    InspectorPanel(selection: $inspectorSection, compact: true)
                                }
                            }
                            .padding(14)
                        }
                    }
                }
                .animation(.easeOut(duration: 0.16), value: sidebarVisible)
            }
        }
        .onOpenURL { url in
            store.accept(url: url)
        }
        .onChange(of: store.result?.output) { _, output in
            if output != nil {
                inspectorSection = .results
                sidebarVisible = true
            } else if store.selectedFile != nil, inspectorSection == .results {
                inspectorSection = .plan
            }
        }
        .onChange(of: store.planPreview?.filename) { _, filename in
            if filename != nil {
                inspectorSection = .results
                sidebarVisible = true
            } else if store.result == nil, store.selectedFile != nil, inspectorSection == .results {
                inspectorSection = .plan
            }
        }
        .onChange(of: store.selectedFile?.path) { _, path in
            if path != nil {
                inspectorSection = .plan
            }
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

    private func primaryWorkspace(availableHeight: CGFloat) -> some View {
        VStack(spacing: 10) {
            ModelPreviewCard()
                .frame(minHeight: max(520, availableHeight - 186))
            ActivityPanel(isExpanded: $activityExpanded)
        }
        .layoutPriority(1)
    }
}

private enum InspectorSection: String, CaseIterable, Identifiable {
    case plan
    case filaments
    case results

    var id: Self { self }

    var title: String {
        switch self {
        case .plan: return "Plan"
        case .filaments: return "Filaments"
        case .results: return "Results"
        }
    }

    var icon: String {
        switch self {
        case .plan: return "slider.horizontal.3"
        case .filaments: return "circle.grid.3x3.fill"
        case .results: return "checkmark.seal"
        }
    }
}

private struct InspectorPanel: View {
    @Binding var selection: InspectorSection
    var compact = false

    var body: some View {
        VStack(spacing: 0) {
            Picker("Inspector", selection: $selection) {
                ForEach(InspectorSection.allCases) { section in
                    Label(section.title, systemImage: section.icon).tag(section)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(12)

            Divider().overlay(Color.studioBorder)

            ScrollView {
                Group {
                    switch selection {
                    case .plan:
                        ConversionControlsCard()
                    case .filaments:
                        InventoryCard()
                    case .results:
                        PaletteResultsCard()
                            .frame(minHeight: compact ? 480 : 560)
                    }
                }
                .padding(12)
            }
            .scrollIndicators(.visible)
        }
        .frame(maxHeight: compact ? nil : .infinity, alignment: .top)
        .background(Color.studioSidebar)
    }
}

private struct ActivityPanel: View {
    @EnvironmentObject private var store: StudioStore
    @Binding var isExpanded: Bool

    private var isBusy: Bool {
        store.isWorking || store.isPlanningPreview || store.isBuildingPreview
    }

    var body: some View {
        VStack(spacing: 0) {
            if isBusy {
                ProgressView(value: store.progress)
                    .progressViewStyle(.linear)
                    .tint(.studioAccent)
            }

            DisclosureGroup(isExpanded: $isExpanded) {
                VStack(alignment: .leading, spacing: 7) {
                    Label(store.timingMessage, systemImage: "clock")
                        .foregroundStyle(Color.studioAccent)
                        .textSelection(.enabled)
                    ForEach(Array(store.activityMessages.reversed().enumerated()), id: \.offset) { _, message in
                        Text(message).textSelection(.enabled)
                    }
                    if let notice = store.inspection?.previewNotice {
                        Text(notice)
                    }
                    if let preview = store.planPreview {
                        Text("Plan preview: \(preview.realSlots) physical + \(preview.outputSlots - preview.realSlots) mixed slots. No output file written.")
                            .foregroundStyle(Color.studioAccent)
                    }
                    ForEach(store.result?.warnings ?? [], id: \.self) { warning in
                        Text(warning).foregroundStyle(Color.studioWarning)
                    }
                }
                .font(.caption)
                .foregroundStyle(Color.studioSecondaryText)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 10)
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: store.result == nil ? "waveform.path.ecg" : "checkmark.shield.fill")
                        .foregroundStyle(store.result == nil ? Color.studioAccent : Color.studioSuccess)
                    Text(store.status)
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Color.studioPrimaryText)
                        .lineLimit(1)
                    Spacer()
                    if isBusy {
                        Text("\(Int(store.progress * 100))%")
                            .font(.caption.monospacedDigit().weight(.semibold))
                            .foregroundStyle(Color.studioAccent)
                    }
                    Label("Activity", systemImage: "list.bullet.rectangle")
                        .font(.caption)
                        .foregroundStyle(Color.studioTertiaryText)
                }
            }
            .padding(11)
        }
        .background(Color.studioPanel)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.studioBorder, lineWidth: 1)
        }
    }
}

private struct StudioBackground: View {
    var body: some View {
        Color.studioCanvas.ignoresSafeArea()
    }
}

private struct HeaderView: View {
    @EnvironmentObject private var store: StudioStore
    @Binding var sidebarVisible: Bool
    let compact: Bool

    private var statusTitle: String {
        if store.isWorking || store.isPlanningPreview || store.isBuildingPreview { return "Processing" }
        if store.result != nil { return "Validated" }
        if store.selectedFile != nil { return "Ready to plan" }
        return "Ready"
    }

    private var statusIcon: String {
        if store.isWorking || store.isPlanningPreview || store.isBuildingPreview { return "circle.dotted" }
        if store.result != nil { return "checkmark.seal.fill" }
        return "circle.fill"
    }

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.studioAccent)
                Image(systemName: "cube.transparent.fill")
                    .font(.system(size: 19, weight: .semibold))
                    .foregroundStyle(Color.studioCanvas)
            }
            .frame(width: 38, height: 38)

            VStack(alignment: .leading, spacing: 1) {
                Text("FullSpectrum Studio")
                    .font(.system(size: 19, weight: .semibold))
                    .foregroundStyle(Color.studioPrimaryText)
                Text(store.selectedFile?.lastPathComponent ?? "Painted palette reduction")
                    .font(.caption)
                    .foregroundStyle(Color.studioTertiaryText)
                    .lineLimit(1)
            }

            Spacer(minLength: 12)

            StatusPill(
                title: statusTitle,
                icon: statusIcon,
                tint: store.result == nil ? .studioAccent : .studioSuccess
            )

            if store.isWorking || store.isPlanningPreview || store.isBuildingPreview {
                Button {
                    store.cancelActiveOperation()
                } label: {
                    Image(systemName: "stop.fill")
                }
                .buttonStyle(StudioIconButtonStyle(tint: .red))
                .help(store.isBuildingPreview ? "Stop preview" : "Cancel active operation")
            }

            Button {
                store.chooseSourceFile()
            } label: {
                if compact { Image(systemName: "folder.badge.plus") }
                else { Label("Open", systemImage: "folder.badge.plus") }
            }
            .buttonStyle(StudioButtonStyle())
            .help("Open a painted source project")

            Button {
                store.chooseReferenceFile()
            } label: {
                if compact { Image(systemName: "photo.on.rectangle") }
                else { Label("Reference", systemImage: "photo.on.rectangle") }
            }
            .buttonStyle(StudioButtonStyle())
            .help("Choose a visual reference")

            Button {
                sidebarVisible.toggle()
            } label: {
                Image(systemName: "sidebar.right")
            }
            .buttonStyle(StudioIconButtonStyle())
            .help(sidebarVisible ? "Hide inspector" : "Show inspector")

            VersionLabel()
        }
    }
}

private struct VersionLabel: View {
    private var text: String {
        let info = Bundle.main.infoDictionary ?? [:]
        let version = info["CFBundleShortVersionString"] as? String ?? "dev"
        let build = info["CFBundleVersion"] as? String
        return build.map { "v\(version) (\($0))" } ?? "v\(version)"
    }

    var body: some View {
        Text(text)
            .font(.caption2.monospacedDigit())
            .foregroundStyle(Color.studioTertiaryText)
            .accessibilityLabel("Version \(text)")
    }
}

private struct StatusPill: View {
    let title: String
    let icon: String
    let tint: Color

    var body: some View {
        Label(title, systemImage: icon)
            .font(.caption.weight(.semibold))
            .foregroundStyle(tint)
            .padding(.horizontal, 10)
            .frame(height: 30)
            .background(tint.opacity(0.1), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .stroke(tint.opacity(0.25), lineWidth: 1)
            }
    }
}

struct StudioButtonStyle: ButtonStyle {
    var prominent = false
    var tint: Color = .studioAccent

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.callout.weight(.semibold))
            .foregroundStyle(prominent ? Color.studioCanvas : Color.studioPrimaryText)
            .padding(.horizontal, 13)
            .frame(minHeight: 34)
            .background {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(prominent ? tint.opacity(configuration.isPressed ? 0.78 : 1) : Color.white.opacity(configuration.isPressed ? 0.10 : 0.06))
            }
            .overlay {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .stroke(prominent ? tint.opacity(0.3) : Color.studioBorder, lineWidth: 1)
            }
    }
}

struct StudioIconButtonStyle: ButtonStyle {
    var tint: Color = .studioSecondaryText

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(tint)
            .frame(width: 34, height: 34)
            .background(Color.white.opacity(configuration.isPressed ? 0.10 : 0.05))
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .stroke(Color.studioBorder, lineWidth: 1)
            }
    }
}

extension Color {
    static let studioCanvas = Color(red: 0.055, green: 0.063, blue: 0.075)
    static let studioChrome = Color(red: 0.070, green: 0.079, blue: 0.091)
    static let studioSidebar = Color(red: 0.063, green: 0.071, blue: 0.083)
    static let studioPanel = Color(red: 0.082, green: 0.092, blue: 0.106)
    static let studioRaised = Color(red: 0.105, green: 0.117, blue: 0.132)
    static let studioBorder = Color.white.opacity(0.10)
    static let studioPrimaryText = Color.white.opacity(0.92)
    static let studioSecondaryText = Color.white.opacity(0.66)
    static let studioTertiaryText = Color.white.opacity(0.43)
    static let studioAccent = Color(red: 0.31, green: 0.73, blue: 0.82)
    static let studioSuccess = Color(red: 0.32, green: 0.76, blue: 0.55)
    static let studioWarning = Color(red: 0.90, green: 0.65, blue: 0.31)
}
