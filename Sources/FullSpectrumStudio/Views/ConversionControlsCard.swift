import SwiftUI

struct ConversionControlsCard: View {
    @EnvironmentObject private var store: StudioStore
    @State private var anchorToolsExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("PLAN SETTINGS")
                .font(.caption.weight(.bold))
                .tracking(1.2)
                .foregroundStyle(Color.studioTertiaryText)

            LiveForecastPanel()

            Divider().overlay(.white.opacity(0.08))

            Picker("Palette strategy", selection: $store.mode) {
                ForEach(PaletteMode.allCases) { mode in
                    Text(mode.title).tag(mode)
                }
            }
            .pickerStyle(.segmented)

            Text(store.mode.explanation)
                .font(.caption)
                .foregroundStyle(.white.opacity(0.54))
            Text("FullSpectrum remaps existing Bambu paint states. It does not repaint, smooth, or clean up the source model's painted regions.")
                .font(.caption2)
                .foregroundStyle(.orange.opacity(0.78))
                .fixedSize(horizontal: false, vertical: true)

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Planner")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.white.opacity(0.42))
                    Spacer(minLength: 10)
                    ReadableMenuPicker(
                        selection: $store.plannerMode,
                        options: PlannerMode.allCases,
                        optionTitle: { $0.title }
                    )
                    .frame(width: 128)
                }
                Text(store.plannerMode.explanation)
                    .font(.caption2)
                    .foregroundStyle(store.plannerMode == .best ? .cyan.opacity(0.68) : .white.opacity(0.5))
                    .fixedSize(horizontal: false, vertical: true)
            }

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Planning sample")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.white.opacity(0.42))
                    Spacer(minLength: 10)
                    ReadableMenuPicker(
                        selection: $store.planningSample,
                        options: PlanningSample.allCases,
                        optionTitle: { $0.title }
                    )
                    .frame(width: 148)
                }
                Text(store.planningSample.explanation)
                    .font(.caption2)
                    .foregroundStyle(store.planningSample == .preview ? .cyan.opacity(0.68) : .white.opacity(0.5))
                    .fixedSize(horizontal: false, vertical: true)
            }

            Text("FILAMENT SOURCE")
                .font(.caption2.weight(.bold))
                .tracking(0.9)
                .foregroundStyle(.white.opacity(0.42))
                .padding(.top, 2)

            ReadableMenuPicker(
                selection: $store.paletteSource,
                options: PaletteSource.allCases,
                optionTitle: { $0.title }
            )

            Text(store.paletteSource.explanation)
                .font(.caption)
                .foregroundStyle(store.paletteSource == .inventory ? .cyan.opacity(0.68) : .orange.opacity(0.76))

            if store.anchorSelectionEnabled {
                DisclosureGroup(isExpanded: $anchorToolsExpanded) {
                    VStack(alignment: .leading, spacing: 10) {
                        VStack(alignment: .leading, spacing: 7) {
                            HStack {
                                Text("Material types")
                                    .font(.caption2.weight(.bold))
                                    .foregroundStyle(.white.opacity(0.46))
                                Spacer()
                                Button("All") {
                                    store.clearMaterialFamilies()
                                }
                                .font(.caption2.weight(.medium))
                                .buttonStyle(.plain)
                                .foregroundStyle(store.activeMaterialFamilies.isEmpty ? .cyan.opacity(0.8) : .white.opacity(0.5))
                            }
                            LazyVGrid(columns: [GridItem(.adaptive(minimum: 118), spacing: 6)], alignment: .leading, spacing: 6) {
                                ForEach(store.materialFamilyOptions) { family in
                                    Button {
                                        store.toggleMaterialFamily(family.series)
                                    } label: {
                                        HStack(spacing: 6) {
                                            Image(systemName: store.activeMaterialFamilies.contains(family.series) ? "checkmark.circle.fill" : "circle")
                                                .imageScale(.small)
                                            Text(family.series)
                                                .lineLimit(1)
                                                .minimumScaleFactor(0.78)
                                            Text("\(family.count)")
                                                .monospacedDigit()
                                                .foregroundStyle(.white.opacity(0.42))
                                        }
                                        .font(.caption2.weight(.medium))
                                        .foregroundStyle(store.activeMaterialFamilies.isEmpty || store.activeMaterialFamilies.contains(family.series) ? .white.opacity(0.82) : .white.opacity(0.48))
                                        .padding(.horizontal, 8)
                                        .frame(minHeight: 26)
                                        .background(.white.opacity(store.activeMaterialFamilies.contains(family.series) ? 0.12 : 0.055), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            Text(store.activeMaterialFamilies.isEmpty ? "Planner may use every allowed Bambu PLA family for this source." : "Planner is limited to: \(store.activeMaterialFamilies.joined(separator: ", ")).")
                                .font(.caption2)
                                .foregroundStyle(.white.opacity(0.44))
                                .fixedSize(horizontal: false, vertical: true)
                        }

                        Divider().overlay(.white.opacity(0.08))

                        VStack(alignment: .leading, spacing: 7) {
                            HStack {
                                Text("Anchor pins")
                                    .font(.caption2.weight(.bold))
                                    .foregroundStyle(.white.opacity(0.46))
                                Spacer()
                                if store.planPreview != nil || store.result != nil {
                                    Button("Use recommended") {
                                        store.useRecommendedAnchors()
                                    }
                                    .font(.caption2.weight(.medium))
                                    .buttonStyle(.plain)
                                    .foregroundStyle(.cyan)
                                }
                                if !store.pinnedAnchorKeys.isEmpty {
                                    Button("Clear") {
                                        store.clearAnchorPins()
                                    }
                                    .font(.caption2.weight(.medium))
                                    .buttonStyle(.plain)
                                    .foregroundStyle(.white.opacity(0.55))
                                }
                            }
                            Text(store.pinnedAnchorSummary)
                                .font(.caption2)
                                .foregroundStyle(.cyan.opacity(0.68))
                            TextField("Search Bambu anchor colors", text: $store.anchorSearch)
                                .textFieldStyle(.roundedBorder)
                                .font(.caption)
                            ScrollView {
                                VStack(spacing: 5) {
                                    ForEach(Array(store.anchorCandidateOptions.prefix(48))) { candidate in
                                        AnchorCandidateButton(
                                            candidate: candidate,
                                            isPinned: store.pinnedAnchorKeys.contains(candidate.key)
                                        ) {
                                            store.toggleAnchorPin(candidate)
                                        }
                                    }
                                }
                            }
                            .frame(maxHeight: 178)
                            if store.anchorCandidateOptions.count > 48 {
                                Text("Showing 48 of \(store.anchorCandidateOptions.count). Search or narrow material types.")
                                    .font(.caption2)
                                    .foregroundStyle(.white.opacity(0.42))
                            }
                            Text("Pinned anchors are forced into the plan; FullSpectrum fills the remaining slots with the best Bambu filaments.")
                                .font(.caption2)
                                .foregroundStyle(.white.opacity(0.44))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(.top, 7)
                } label: {
                    HStack {
                        Label("Bambu materials and anchors", systemImage: "scope")
                        Spacer()
                        Text(store.activeMaterialFamilies.isEmpty ? store.pinnedAnchorSummary : "\(store.activeMaterialFamilies.count) type\(store.activeMaterialFamilies.count == 1 ? "" : "s") · \(store.pinnedAnchorSummary)")
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(.white.opacity(0.5))
                    }
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.white.opacity(0.76))
                }
            }

            if store.paletteSource == .catalog || store.paletteSource == .allBambu {
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text("Catalog region")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.white.opacity(0.42))
                        Spacer(minLength: 10)
                        ReadableMenuPicker(
                            selection: Binding(
                                get: { store.catalogRegion },
                                set: { store.catalogRegion = $0 }
                            ),
                            options: CatalogRegion.allCases,
                            optionTitle: { $0.title }
                        )
                        .frame(width: 172)
                    }
                    Text("Planning region only. FullSpectrum does not check live Bambu store stock.")
                        .font(.caption2)
                        .foregroundStyle(.white.opacity(0.48))
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            HStack {
                ReadableMenuPicker(
                    selection: $store.realSlots,
                    options: RealSlotSelection.allCases,
                    optionTitle: { $0.title }
                )
                .frame(width: 126)

                Toggle("Auto-open", isOn: $store.autoOpenValidatedOutput)
                    .toggleStyle(.switch)
                    .font(.caption)
            }
            .foregroundStyle(.white.opacity(0.7))

            if store.autoOpenValidatedOutput {
                ReadableMenuPicker(
                    selection: Binding(
                        get: { store.outputApplication },
                        set: { store.outputApplication = $0 }
                    ),
                    options: OutputApplication.allCases,
                    optionTitle: { $0.title }
                )
                .help("FullSpectrum validates first, then hands the saved project to the selected slicer.")
            }

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(store.smartQuality ? "Smart quality vs waste" : "Quality vs waste")
                    Spacer()
                    if store.smartQuality {
                        Text(store.result?.quality.resolvedQualityBias.map { "auto \($0)" } ?? "auto")
                            .monospacedDigit()
                    } else {
                        Text("\(Int(store.qualityBias))")
                            .monospacedDigit()
                    }
                }
                .font(.caption)
                .foregroundStyle(.white.opacity(0.7))
                Toggle("Auto-select high-fidelity quality and anchor parents", isOn: $store.smartQuality)
                    .font(.caption2)
                    .toggleStyle(.checkbox)
                    .foregroundStyle(.white.opacity(0.62))
                Slider(value: $store.qualityBias, in: 0...100, step: 5) {
                    Text("Quality versus waste")
                }
                .disabled(store.smartQuality)
                .opacity(store.smartQuality ? 0.45 : 1)
                .tint(.cyan)
                Text(store.smartQuality ? "Smart: tests practical, balanced and high-fidelity math plans with the selected planner, then keeps the best validated palette." :
                        store.qualityBias < 40 ? "Practical: requires stronger visual gains before creating mixes." :
                        store.qualityBias > 75 ? "Detail: searches denser Bambu-style 2/3-color recipes and parent anchors." :
                        "Balanced: suppresses weak mixes while keeping visible improvements.")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.48))
                Text("Auto keeps 2-6 physical slots so slot 7 can stay available for support; 7/8 are experimental manual choices.")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.42))
                    .fixedSize(horizontal: false, vertical: true)
            }
            .help("Smart mode chooses the quality threshold and physical anchor colors together, based on the final Bambu-reconstructed palette after mixed recipes are generated.")

            if let resolved = store.result?.quality.resolvedQualityBias, store.result?.quality.qualityBiasMode == "auto" {
                HStack(spacing: 6) {
                    Image(systemName: "sparkles")
                    Text("Smart plan chose quality \(resolved)/100 for this model.")
                        .monospacedDigit()
                }
                .font(.caption2.weight(.medium))
                .foregroundStyle(.cyan.opacity(0.74))
            }

            Label(store.mixPrediction.title, systemImage: "checkmark.shield")
                .font(.caption.weight(.medium))
                .foregroundStyle(.green.opacity(0.84))
            Text(store.mixPrediction.explanation)
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.48))

            if store.selectedFile != nil {
                Label(store.optionEstimateMessage, systemImage: "timer")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.cyan.opacity(0.72))
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
                    .help("Rough local estimate for the current model and options. It improves after successful local runs.")
            }

            HStack(spacing: 8) {
                Button(store.referenceURL == nil ? "Add Reference" : "Change Reference") {
                    store.chooseReferenceFile()
                }
                .font(.caption.weight(.medium))
                .buttonStyle(.plain)
                .foregroundStyle(.cyan)

                if store.paletteSource == .custom {
                    Button(store.customPaletteURL == nil ? "Choose Library" : "Change Library") {
                        store.chooseCustomPaletteFile()
                    }
                    .font(.caption.weight(.medium))
                    .buttonStyle(.plain)
                    .foregroundStyle(.cyan)
                }
                if store.selectedFile?.pathExtension.lowercased() == "obj" {
                    Button(store.textureOverrideURL == nil ? "Add OBJ Texture" : "Change OBJ Texture") {
                        store.chooseTextureFile()
                    }
                    .font(.caption.weight(.medium))
                    .buttonStyle(.plain)
                    .foregroundStyle(.cyan)
                    .help("Choose the PNG/JPEG base-color texture when the OBJ has no material link")
                }
                Spacer()
            }
            if let reference = store.referenceURL {
                Text("Reference: \(reference.lastPathComponent)")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.52))
                    .lineLimit(1)
            }
            if let texture = store.textureOverrideURL,
               store.selectedFile?.pathExtension.lowercased() == "obj" {
                Text("OBJ color texture: \(texture.lastPathComponent)")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.52))
                    .lineLimit(1)
            }

            if store.isWorking || store.isPlanningPreview || store.isBuildingPreview || store.progress > 0 {
                VStack(alignment: .leading, spacing: 7) {
                    HStack {
                        Text(store.progressMessage)
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.65))
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer()
                        Text("\(Int(store.progress * 100))%")
                            .font(.caption.monospacedDigit().weight(.medium))
                            .foregroundStyle(.cyan.opacity(0.9))
                    }
                    ProgressView(value: store.progress)
                        .progressViewStyle(.linear)
                        .tint(.cyan)
                    Label(store.timingMessage, systemImage: "clock")
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.cyan.opacity(0.72))
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                    ForEach(Array(store.activityMessages.suffix(3).enumerated()), id: \.offset) { _, message in
                        if message != store.progressMessage {
                            Text(message)
                                .font(.caption2)
                                .foregroundStyle(.white.opacity(0.42))
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(.vertical, 2)
            }

            HStack(spacing: 10) {
                Button {
                    store.previewPlan()
                } label: {
                    HStack(spacing: 8) {
                        if store.isPlanningPreview {
                            ProgressView().controlSize(.small)
                        } else {
                            Image(systemName: "eye")
                        }
                        Text(store.isPlanningPreview ? "Previewing..." : "Preview Plan")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(StudioButtonStyle())
                .disabled(store.selectedFile == nil || store.isWorking || store.isPlanningPreview || store.isBuildingPreview)
                .help("Run the selected planner options without writing a 3MF")

                Button {
                    store.convert()
                } label: {
                    HStack(spacing: 8) {
                        if store.isWorking {
                            ProgressView().controlSize(.small)
                        } else {
                            Image(systemName: "wand.and.stars")
                        }
                        Text(store.isWorking ? "Working..." : "Compose Palette")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(StudioButtonStyle(prominent: true))
                .disabled(store.selectedFile == nil || store.isWorking || store.isPlanningPreview)
            }

            if store.result != nil || store.isWorking || store.isPlanningPreview || store.isBuildingPreview {
                HStack(spacing: 8) {
                    if store.result != nil {
                        Button {
                            store.revealOutput()
                        } label: {
                            Label("Reveal Output", systemImage: "folder")
                        }
                        .buttonStyle(StudioButtonStyle())
                        .help("Reveal the validated output in Finder")
                    }
                    Spacer()
                    if store.isWorking || store.isPlanningPreview || store.isBuildingPreview {
                        Button {
                            store.cancelActiveOperation()
                        } label: {
                            Label(store.isBuildingPreview ? "Stop Preview" : "Cancel", systemImage: "stop.fill")
                        }
                        .buttonStyle(StudioButtonStyle(tint: .red))
                        .help("Stop the active operation")
                    }
                }
            }

            if store.result != nil {
                Button {
                    store.openOutput()
                } label: {
                    Label("Open Validated File in \(store.outputApplication.title)", systemImage: "arrow.up.forward.app")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(StudioButtonStyle())
                .help("Open the saved validated .3mf in \(store.outputApplication.title)")
            }

            Toggle("Restore last local session", isOn: $store.restoreLastSession)
                .toggleStyle(.switch)
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.52))
        }
        .padding(17)
        .background(CardSurface())
        .onChange(of: store.paletteSource) { _, source in
            store.plannerInputsChanged()
            if source == .exactCMYKW {
                store.mode = .cmykw
            }
        }
        .onChange(of: store.mode) { _, mode in
            store.plannerInputsChanged()
            if mode != .cmykw && store.paletteSource == .exactCMYKW {
                store.paletteSource = .catalog
            }
        }
        .onChange(of: store.plannerMode) { _, _ in store.plannerInputsChanged() }
        .onChange(of: store.planningSample) { _, _ in store.plannerInputsChanged() }
        .onChange(of: store.realSlots) { _, _ in store.plannerInputsChanged() }
        .onChange(of: store.smartQuality) { _, _ in store.plannerInputsChanged() }
        .onChange(of: store.qualityBias) { _, _ in store.plannerInputsChanged() }
        .onChange(of: store.catalogRegion) { _, _ in store.plannerInputsChanged() }
        .onChange(of: store.automaticPlanPreview) { _, _ in store.automaticPreviewSettingChanged() }
    }
}

private struct LiveForecastPanel: View {
    @EnvironmentObject private var store: StudioStore

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Label("LIVE FORECAST", systemImage: "sparkles")
                    .font(.caption.weight(.bold))
                    .tracking(0.9)
                    .foregroundStyle(Color.studioAccent)
                Spacer()
                Toggle("Auto", isOn: $store.automaticPlanPreview)
                    .toggleStyle(.switch)
                    .controlSize(.small)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(Color.studioSecondaryText)
            }

            if let quality = store.forecastQuality {
                HStack(alignment: .center, spacing: 14) {
                    ForecastAccuracyGauge(score: quality.qualityScore)

                    VStack(alignment: .leading, spacing: 7) {
                        ForecastMetricRow(
                            title: "Confidence",
                            value: "\(Int(quality.confidenceScore.rounded()))%"
                        )
                        ForecastMetricRow(
                            title: "Worst match",
                            value: String(format: "dE %.1f", quality.maximumDeltaE)
                        )
                        if let slots = store.forecastSlotSummary {
                            ForecastMetricRow(title: "Plan", value: slots)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                if !store.forecastOutputColors.isEmpty {
                    ForecastPaletteStrip(colors: store.forecastOutputColors)
                }

                if let match = store.forecastWorstMatch, match.deltaE > 3 {
                    WorstMatchNotice(match: match)
                }

                Text("Estimated before slicing and physical calibration")
                    .font(.caption2)
                    .foregroundStyle(Color.studioTertiaryText)
            } else {
                HStack(spacing: 10) {
                    if store.isPlanningPreview {
                        ProgressView().controlSize(.small)
                    } else {
                        Image(systemName: store.selectedFile == nil ? "cube.transparent" : "waveform.path.ecg")
                            .foregroundStyle(Color.studioTertiaryText)
                    }
                    Text(store.selectedFile == nil ? "No model loaded" : "Forecast pending")
                        .font(.callout.weight(.medium))
                        .foregroundStyle(Color.studioSecondaryText)
                    Spacer()
                }
                .frame(minHeight: 52)
            }

            if store.isPlanningPreview {
                ProgressView(value: store.progress)
                    .progressViewStyle(.linear)
                    .tint(Color.studioAccent)
            }
        }
    }
}

private struct ForecastAccuracyGauge: View {
    let score: Double

    private var tint: Color {
        if score >= 88 { return .studioSuccess }
        if score >= 70 { return .studioAccent }
        return .studioWarning
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.white.opacity(0.08), lineWidth: 7)
            Circle()
                .trim(from: 0, to: max(0, min(1, score / 100)))
                .stroke(tint, style: StrokeStyle(lineWidth: 7, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(Int(score.rounded()))%")
                    .font(.title3.monospacedDigit().weight(.bold))
                    .foregroundStyle(Color.studioPrimaryText)
                Text("accuracy")
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundStyle(Color.studioTertiaryText)
            }
        }
        .frame(width: 82, height: 82)
        .accessibilityLabel("Estimated accuracy \(Int(score.rounded())) percent")
    }
}

private struct ForecastMetricRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack(spacing: 8) {
            Text(title)
                .foregroundStyle(Color.studioTertiaryText)
            Spacer(minLength: 4)
            Text(value)
                .monospacedDigit()
                .foregroundStyle(Color.studioPrimaryText)
                .multilineTextAlignment(.trailing)
        }
        .font(.caption.weight(.medium))
    }
}

private struct ForecastPaletteStrip: View {
    let colors: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("EXPECTED PALETTE")
                .font(.caption2.weight(.bold))
                .tracking(0.8)
                .foregroundStyle(Color.studioTertiaryText)
            LazyVGrid(
                columns: [GridItem(.adaptive(minimum: 22, maximum: 34), spacing: 5)],
                alignment: .leading,
                spacing: 5
            ) {
                ForEach(Array(colors.enumerated()), id: \.offset) { _, color in
                    RoundedRectangle(cornerRadius: 4, style: .continuous)
                        .fill(Color(hex: color))
                        .frame(maxWidth: .infinity, minHeight: 24, maxHeight: 24)
                        .overlay {
                            RoundedRectangle(cornerRadius: 4, style: .continuous)
                                .stroke(Color.white.opacity(0.14), lineWidth: 1)
                        }
                }
            }
        }
    }
}

private struct WorstMatchNotice: View {
    @EnvironmentObject private var store: StudioStore
    let match: WorstColorMatch

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .fill(Color(hex: match.targetColor))
                    .frame(width: 24, height: 24)
                Image(systemName: "arrow.right")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(Color.studioTertiaryText)
                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .fill(Color(hex: match.predictedColor))
                    .frame(width: 24, height: 24)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Worst visible match")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Color.studioWarning)
                    Text(String(format: "Slot %d · %.1f%% paint · dE %.1f", match.sourceSlot, match.paintedShare, match.deltaE))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(Color.studioTertiaryText)
                }
                Spacer(minLength: 0)
            }

            if let suggestion = match.suggestedFilament {
                HStack(spacing: 8) {
                    Circle()
                        .fill(Color(hex: suggestion.color))
                        .frame(width: 16, height: 16)
                        .overlay { Circle().stroke(Color.white.opacity(0.16), lineWidth: 1) }
                    Text(suggestion.availability == "not in My Inventory"
                         ? "Missing from My Inventory: \(suggestion.name)"
                         : "Available in My Inventory: \(suggestion.name)")
                        .font(.caption2.weight(.medium))
                        .foregroundStyle(Color.studioSecondaryText)
                        .lineLimit(2)
                    Spacer(minLength: 4)
                    Button {
                        store.applyForecastSuggestion(suggestion)
                    } label: {
                        Label("Use", systemImage: "wand.and.stars")
                    }
                    .buttonStyle(.plain)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Color.studioAccent)
                    .help("Add this filament to the next plan")
                }
            }
        }
        .padding(.vertical, 9)
        .overlay(alignment: .top) { Divider().overlay(Color.studioWarning.opacity(0.25)) }
        .overlay(alignment: .bottom) { Divider().overlay(Color.studioWarning.opacity(0.25)) }
    }
}

private struct AnchorCandidateButton: View {
    let candidate: AnchorCandidate
    let isPinned: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Circle()
                    .fill(Color(hex: candidate.color))
                    .frame(width: 16, height: 16)
                    .overlay { Circle().stroke(.white.opacity(0.18), lineWidth: 1) }
                VStack(alignment: .leading, spacing: 1) {
                    Text(candidate.name)
                        .font(.caption2.weight(.medium))
                        .foregroundStyle(.white.opacity(0.82))
                        .lineLimit(1)
                    Text(anchorDetail)
                        .font(.system(size: 9, weight: .medium, design: .monospaced))
                        .foregroundStyle(.white.opacity(0.42))
                        .lineLimit(1)
                }
                Spacer(minLength: 6)
                Image(systemName: isPinned ? "checkmark.circle.fill" : "plus.circle")
                    .foregroundStyle(isPinned ? .cyan : .white.opacity(0.38))
                    .imageScale(.small)
            }
            .padding(.horizontal, 7)
            .frame(minHeight: 34)
            .background(.white.opacity(isPinned ? 0.10 : 0.04), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    private var anchorDetail: String {
        if let grams = candidate.remainingGrams {
            return "\(candidate.series) · \(candidate.color) · \(Int(grams))g"
        }
        return "\(candidate.series) · \(candidate.color)"
    }
}

private struct ReadableMenuPicker<Option: Identifiable & Hashable>: View {
    @Binding var selection: Option
    let options: [Option]
    let optionTitle: (Option) -> String

    var body: some View {
        Menu {
            ForEach(options) { option in
                Button {
                    selection = option
                } label: {
                    if option == selection {
                        Label(optionTitle(option), systemImage: "checkmark")
                    } else {
                        Text(optionTitle(option))
                    }
                }
            }
        } label: {
            HStack(spacing: 8) {
                Text(optionTitle(selection))
                    .lineLimit(1)
                    .minimumScaleFactor(0.82)
                Spacer(minLength: 8)
                Image(systemName: "chevron.up.chevron.down")
                    .imageScale(.small)
                    .foregroundStyle(.white.opacity(0.56))
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white.opacity(0.94))
            .padding(.horizontal, 12)
            .frame(minHeight: 34)
            .background {
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .fill(.white.opacity(0.1))
            }
            .overlay {
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .stroke(.white.opacity(0.13), lineWidth: 1)
            }
        }
        .buttonStyle(.plain)
        .menuStyle(.button)
    }
}
