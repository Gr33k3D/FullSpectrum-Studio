import SwiftUI

struct PaletteResultsCard: View {
    @EnvironmentObject private var store: StudioStore

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
                    if let referenceScore = result.quality.referenceSimilarityScore {
                        MetricChip(title: "REFERENCE", value: String(format: "%.0f / 100", referenceScore))
                    }
                }

                if result.preservation.geometryPreserved && result.preservation.textureResourcesPreserved {
                    Label("Geometry, UV meaning and texture resources verified unchanged", systemImage: "checkmark.shield")
                        .font(.caption)
                        .foregroundStyle(.green.opacity(0.84))
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
                }

                ScrollView {
                    LazyVStack(spacing: 7) {
                        ForEach(result.mixedRecipes) { recipe in
                            RecipeRow(recipe: recipe)
                        }
                    }
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
            return "\(anchor.filamentID)  \(Int(grams)) g left"
        }
        if paletteSource == PaletteSource.exactCMYKW.rawValue {
            return "\(anchor.filamentID)  load physical match"
        }
        return "\(anchor.filamentID)  catalog"
    }
}

private struct RecipeRow: View {
    let recipe: RecipeItem

    var body: some View {
        HStack(spacing: 9) {
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .fill(Color(hex: recipe.targetColor))
                .frame(width: 26, height: 26)
            Text("\(recipe.newSlot)")
                .font(.caption.monospacedDigit().weight(.semibold))
                .foregroundStyle(.white.opacity(0.6))
                .frame(width: 23, alignment: .leading)
            Text(recipe.components.replacingOccurrences(of: ",", with: " + "))
                .font(.caption.monospaced())
                .foregroundStyle(.white.opacity(0.86))
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
            }
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 7)
        .background(.white.opacity(0.026), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
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
