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

            Text("FILAMENT SOURCE")
                .font(.caption2.weight(.bold))
                .tracking(0.9)
                .foregroundStyle(.white.opacity(0.42))
                .padding(.top, 2)

            Picker("Filament source", selection: $store.paletteSource) {
                ForEach(PaletteSource.allCases) { source in
                    Text(source.title).tag(source)
                }
            }
            .pickerStyle(.menu)

            Text(store.paletteSource.explanation)
                .font(.caption)
                .foregroundStyle(store.paletteSource == .inventory ? .cyan.opacity(0.68) : .orange.opacity(0.76))

            HStack {
                Picker("Physical slots", selection: $store.realSlots) {
                    ForEach(RealSlotSelection.allCases) { count in
                        Text(count.title).tag(count)
                    }
                }
                .pickerStyle(.menu)

                Toggle("Auto-open", isOn: $store.autoOpenValidatedOutput)
                    .toggleStyle(.switch)
                    .font(.caption)
            }
            .foregroundStyle(.white.opacity(0.7))

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Quality vs waste")
                    Spacer()
                    Text("\(Int(store.qualityBias))")
                        .monospacedDigit()
                }
                .font(.caption)
                .foregroundStyle(.white.opacity(0.7))
                Slider(value: $store.qualityBias, in: 0...100, step: 5) {
                    Text("Quality versus waste")
                }
                .tint(.cyan)
                Text(store.qualityBias < 40 ? "Practical: requires stronger visual gains before creating mixes." :
                        store.qualityBias > 75 ? "Detail: permits more logical mixes and three-color candidates." :
                        "Balanced: suppresses weak mixes while keeping visible improvements.")
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.48))
            }

            Picker("Mix prediction", selection: $store.mixPrediction) {
                ForEach(MixPrediction.allCases) { prediction in
                    Text(prediction.title).tag(prediction)
                }
            }
            .pickerStyle(.menu)
            Text(store.mixPrediction.explanation)
                .font(.caption2)
                .foregroundStyle(store.mixPrediction == .perceptual ? .white.opacity(0.48) : .orange.opacity(0.84))

            HStack(spacing: 10) {
                Button(store.referenceURL == nil ? "Add Reference" : "Change Reference") {
                    store.showingReferenceImporter = true
                }
                .font(.caption.weight(.medium))
                .buttonStyle(.plain)
                .foregroundStyle(.cyan)

                if store.paletteSource == .custom {
                    Button(store.customPaletteURL == nil ? "Choose Library" : "Change Library") {
                        store.showingCustomPaletteImporter = true
                    }
                    .font(.caption.weight(.medium))
                    .buttonStyle(.plain)
                    .foregroundStyle(.cyan)
                }
                if store.selectedFile?.pathExtension.lowercased() == "obj" {
                    Button(store.textureOverrideURL == nil ? "Add OBJ Texture" : "Change OBJ Texture") {
                        store.showingTextureImporter = true
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

            if store.isWorking || store.progress > 0 {
                VStack(alignment: .leading, spacing: 7) {
                    HStack {
                        Text(store.progressMessage)
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.65))
                            .lineLimit(1)
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
                        Label("Show Output", systemImage: "folder")
                    }
                    .buttonStyle(StudioButtonStyle())
                    .help("Reveal the validated output in Finder")
                }
                if store.isWorking {
                    Button("Cancel") { store.cancelConversion() }
                        .buttonStyle(StudioButtonStyle())
                        .help("Stop the active conversion")
                }
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
