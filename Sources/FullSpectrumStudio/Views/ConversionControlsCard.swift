import SwiftUI

struct ConversionControlsCard: View {
    @EnvironmentObject private var store: StudioStore

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("PALETTE ENGINE")
                .font(.caption.weight(.bold))
                .tracking(1.2)
                .foregroundStyle(.white.opacity(0.5))

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
                Toggle("Auto-select best quality and anchor parents", isOn: $store.smartQuality)
                    .font(.caption2)
                    .toggleStyle(.checkbox)
                    .foregroundStyle(.white.opacity(0.62))
                Slider(value: $store.qualityBias, in: 0...100, step: 5) {
                    Text("Quality versus waste")
                }
                .disabled(store.smartQuality)
                .opacity(store.smartQuality ? 0.45 : 1)
                .tint(.cyan)
                Text(store.smartQuality ? "Smart: tests practical, balanced and detail plans, then keeps the best validated palette." :
                        store.qualityBias < 40 ? "Practical: requires stronger visual gains before creating mixes." :
                        store.qualityBias > 75 ? "Detail: permits more logical mixes and three-color candidates." :
                        "Balanced: suppresses weak mixes while keeping visible improvements.")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.48))
            }
            .help("Smart mode chooses the quality threshold and physical anchor colors together, based on the final palette after mixed recipes are generated.")

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

            HStack(spacing: 10) {
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

            if store.isWorking || store.isBuildingPreview || store.progress > 0 {
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
                }
                .padding(.vertical, 2)
            }

            HStack(spacing: 10) {
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
                .disabled(store.selectedFile == nil || store.isWorking)

                if store.result != nil {
                    Button {
                        store.revealOutput()
                    } label: {
                        Label("Open Folder", systemImage: "folder")
                    }
                    .buttonStyle(StudioButtonStyle())
                        .help("Reveal the validated output in Finder")
                }
                if store.isWorking {
                    Button("Cancel") { store.cancelConversion() }
                        .buttonStyle(StudioButtonStyle())
                        .help("Stop the active conversion")
                } else if store.isBuildingPreview {
                    Button("Stop Preview") { store.cancelPreview() }
                        .buttonStyle(StudioButtonStyle())
                        .help("Stop only the optional interactive preview build")
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

            HStack(spacing: 10) {
                Image(systemName: store.result == nil ? "waveform.path.ecg" : "checkmark.shield.fill")
                    .foregroundStyle(store.result == nil ? .cyan.opacity(0.7) : .green)
                Text(store.status)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.66))
                    .lineLimit(2)
                Spacer()
            }
            Toggle("Restore last local session", isOn: $store.restoreLastSession)
                .toggleStyle(.switch)
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.52))
        }
        .padding(17)
        .background(CardSurface())
        .onChange(of: store.paletteSource) { _, source in
            if source == .exactCMYKW {
                store.mode = .cmykw
            }
        }
        .onChange(of: store.mode) { _, mode in
            if mode != .cmykw && store.paletteSource == .exactCMYKW {
                store.paletteSource = .catalog
            }
        }
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
