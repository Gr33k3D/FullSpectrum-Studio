import SwiftUI

struct PaletteResultsCard: View {
    @EnvironmentObject private var store: StudioStore
    @State private var showingColorDebug = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(store.result == nil ? "OUTPUT PALETTE" : "VALIDATED PALETTE")
                    .font(.caption.weight(.bold))
                    .tracking(1.2)
                    .foregroundStyle(.white.opacity(0.5))
                Spacer()
                if let result = store.result {
                    Text("\(result.realSlots) real + \(result.outputSlots - result.realSlots) mixed")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.green.opacity(0.9))
                }
            }

            if let result = store.result {
                AnchorGrid(anchors: result.anchors, paletteSource: result.paletteSource)

                Divider().overlay(.white.opacity(0.1))

                HStack(spacing: 18) {
                    MetricChip(title: "QUALITY", value: String(format: "%.0f / 100", result.quality.qualityScore))
                    MetricChip(title: "MEAN ERROR", value: String(format: "dE %.1f", result.quality.estimatedDeltaE))
                    MetricChip(title: "CONFIDENCE", value: String(format: "%.0f / 100", result.quality.confidenceScore))
                }
                HStack(spacing: 18) {
                    if let referenceScore = result.quality.referenceSimilarityScore {
                        MetricChip(title: "REFERENCE", value: String(format: "%.0f / 100", referenceScore))
                    }
                    if let contrast = result.quality.contrastRetention {
                        MetricChip(title: "CONTRAST", value: String(format: "%.0f%%", contrast))
                    }
                    MetricChip(title: "MIXED PAINT", value: String(format: "%.0f%%", result.printability.paintedMixedShare))
                }

                if result.preservation.geometryPreserved && result.preservation.textureResourcesPreserved && result.preservation.paintRemapVerified {
                    Label("Geometry, UV, textures and decoded paint remap verified", systemImage: "checkmark.shield")
                        .font(.caption)
                        .foregroundStyle(.green.opacity(0.84))
                }
                if result.colorValidation.verified {
                    Label(
                        "Bambu loaded-color reconstruction verified (max sync dE \(String(format: "%.2f", result.colorValidation.maximumDeltaE)))",
                        systemImage: "eyedropper.halffull"
                    )
                    .font(.caption)
                    .foregroundStyle(.green.opacity(0.84))
                }
                Label("\(result.printability.difficulty) printability complexity; actual time and material require slicing", systemImage: "printer")
                    .font(.caption)
                    .foregroundStyle(.cyan.opacity(0.76))
                ForEach(result.printability.recommendations, id: \.self) { recommendation in
                    Text("Suggestion: \(recommendation)")
                        .font(.caption)
                        .foregroundStyle(.cyan.opacity(0.76))
                }
                if let next = result.recommendation {
                    HStack(spacing: 8) {
                        Circle().fill(Color(hex: next.color)).frame(width: 14, height: 14)
                        Text("Next anchor: \(next.name) could reduce estimated error by \(String(format: "%.1f", next.estimatedDeltaEReduction)) dE")
                    }
                    .font(.caption)
                    .foregroundStyle(.cyan.opacity(0.84))
                }
                ForEach(result.warnings, id: \.self) { warning in
                    Text(warning)
                        .font(.caption)
                        .foregroundStyle(.orange.opacity(0.9))
                }

                HStack {
                    Text("MIXED RECIPES")
                        .font(.caption2.weight(.bold))
                        .tracking(0.8)
                        .foregroundStyle(.white.opacity(0.42))
                    Spacer()
                    Button("Open Output") { store.openOutput() }
                        .font(.caption.weight(.semibold))
                        .buttonStyle(.plain)
                        .foregroundStyle(.cyan)
                    Button("Color Report") { store.openColorValidationReport() }
                        .font(.caption.weight(.semibold))
                        .buttonStyle(.plain)
                        .foregroundStyle(.cyan)
                }

                ScrollView {
                    LazyVStack(spacing: 7) {
                        ForEach(result.mixedRecipes) { recipe in
                            RecipeRow(recipe: recipe, anchors: result.anchors)
                        }
                    }
                }
                DisclosureGroup("Color Debug View", isExpanded: $showingColorDebug) {
                    VStack(alignment: .leading, spacing: 7) {
                        Text("Target  |  App prediction  |  Exported  |  Bambu loaded")
                            .font(.caption2.monospaced())
                            .foregroundStyle(.white.opacity(0.48))
                        ForEach(result.colorValidation.recipes) { entry in
                            ColorDebugRow(entry: entry)
                        }
                    }
                    .padding(.top, 8)
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(.cyan.opacity(0.9))
                if result.import != nil {
                    Text("Experimental source import was converted through the same paint and preservation validator.")
                        .font(.caption2)
                        .foregroundStyle(.orange.opacity(0.8))
                }
            } else {
                EmptyResultsPanel()
            }
        }
        .padding(17)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(CardSurface())
    }
}

private struct ColorDebugRow: View {
    let entry: ColorValidationItem

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 7) {
                Text("\(entry.newSlot)")
                    .font(.caption2.monospacedDigit())
                    .frame(width: 18, alignment: .leading)
                ForEach(Array([entry.target, entry.appPrediction, entry.exported, entry.bambuLoaded].enumerated()), id: \.offset) { _, hex in
                    RoundedRectangle(cornerRadius: 4, style: .continuous)
                        .fill(Color(hex: hex))
                        .frame(width: 20, height: 20)
                        .overlay { RoundedRectangle(cornerRadius: 4).stroke(.white.opacity(0.14)) }
                }
                Text("\(entry.components) @ \(entry.ratios)")
                    .font(.caption2.monospaced())
                    .lineLimit(1)
                Spacer()
                Text(String(format: "target dE %.1f  sync %.2f", entry.targetDeltaE, entry.predictionDeltaE))
                    .font(.caption2.monospacedDigit())
            }
            Text("\(entry.target)  |  \(entry.appPrediction)  |  \(entry.exported)  |  \(entry.bambuLoaded)")
                .font(.caption2.monospaced())
                .foregroundStyle(.white.opacity(0.48))
        }
        .foregroundStyle(.white.opacity(0.65))
    }
}

private struct MetricChip: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.caption2.weight(.bold))
                .foregroundStyle(.white.opacity(0.4))
            Text(value)
                .font(.caption.monospacedDigit().weight(.medium))
                .foregroundStyle(.cyan.opacity(0.86))
        }
    }
}

private struct AnchorGrid: View {
    let anchors: [AnchorFilament]
    let paletteSource: String
    private let columns = [GridItem(.flexible()), GridItem(.flexible())]

    var body: some View {
        LazyVGrid(columns: columns, spacing: 8) {
            ForEach(anchors) { anchor in
                HStack(spacing: 9) {
                    Circle()
                        .fill(Color(hex: anchor.color))
                        .frame(width: 25, height: 25)
                        .overlay { Circle().stroke(.white.opacity(0.18), lineWidth: 1) }
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Slot \(anchor.slot)  \(anchor.name)")
                            .font(.caption.weight(.medium))
                            .foregroundStyle(.white.opacity(0.88))
                            .lineLimit(1)
                        Text(secondaryText(for: anchor))
                            .font(.caption2.monospaced())
                            .foregroundStyle(.white.opacity(0.45))
                    }
                    Spacer(minLength: 0)
                }
                .padding(8)
                .background(.white.opacity(0.035), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            }
        }
    }

    private func secondaryText(for anchor: AnchorFilament) -> String {
        if let grams = anchor.remainingGrams {
            return "\(anchor.color)  \(Int(grams)) g left"
        }
        if paletteSource == PaletteSource.exactCMYKW.rawValue {
            return "\(anchor.color)  load physical match"
        }
        return "\(anchor.color)  catalog"
    }
}

private struct RecipeRow: View {
    let recipe: RecipeItem
    let anchors: [AnchorFilament]

    private var componentNames: String {
        recipe.components.split(separator: ",").compactMap { value -> String? in
            guard let slot = Int(value), slot > 0, slot <= anchors.count else { return nil }
            return anchors[slot - 1].name
        }.joined(separator: " + ")
    }

    var body: some View {
        HStack(spacing: 9) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 4) {
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .fill(Color(hex: recipe.targetColor))
                    Image(systemName: "arrow.right")
                        .font(.system(size: 8, weight: .bold))
                        .foregroundStyle(.white.opacity(0.38))
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .fill(Color(hex: recipe.preview))
                }
                .frame(width: 59, height: 21)
                Text("target -> output")
                    .font(.system(size: 8, weight: .medium, design: .monospaced))
                    .foregroundStyle(.white.opacity(0.34))
            }
            Text("\(recipe.newSlot)")
                .font(.caption.monospacedDigit().weight(.semibold))
                .foregroundStyle(.white.opacity(0.6))
                .frame(width: 23, alignment: .leading)
            Text(componentNames.isEmpty ? recipe.label : componentNames)
                .font(.caption)
                .foregroundStyle(.white.opacity(0.86))
                .lineLimit(1)
            Text(recipe.ratios)
                .font(.caption2.monospaced())
                .foregroundStyle(.white.opacity(0.46))
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                if let availableGrams = recipe.availableGrams {
                    Text(String(format: "up to %.0f g", availableGrams))
                        .font(.caption2.monospacedDigit().weight(.medium))
                        .foregroundStyle(.cyan.opacity(0.7))
                }
                Text(String(format: "dE %.1f", recipe.deltaE))
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(.white.opacity(0.48))
                if recipe.visualGain > 0 {
                    Text(String(format: "+%.1f gain", recipe.visualGain))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.green.opacity(0.72))
                }
            }
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 7)
        .background(.white.opacity(0.026), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
        .help("Left swatch is the original painted target; right swatch is Bambu Studio's reconstructed exported color.")
    }
}

private struct EmptyResultsPanel: View {
    var body: some View {
        VStack(spacing: 14) {
            Spacer()
            Image(systemName: "circle.hexagongrid.fill")
                .font(.system(size: 34))
                .foregroundStyle(.cyan.opacity(0.36))
            Text("Your physical filaments and generated mixes will appear here.")
                .font(.callout)
                .foregroundStyle(.white.opacity(0.48))
                .multilineTextAlignment(.center)
                .frame(maxWidth: 270)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }
}
