import SwiftUI

struct InventoryCard: View {
    @EnvironmentObject private var store: StudioStore

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack {
                Text("BAMBU INVENTORY BETA")
                    .font(.caption.weight(.bold))
                    .tracking(1.2)
                    .foregroundStyle(.white.opacity(0.5))
                Spacer()
                Text("READ ONLY SYNC")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(.cyan.opacity(0.8))
                Button {
                    store.refreshInventory()
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption.weight(.semibold))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white.opacity(0.7))
                .disabled(store.isRefreshingInventory)
            }

            if let inventory = store.inventory {
                HStack(spacing: 20) {
                    InventoryStat(value: "\(inventory.usableCount)", label: "Active PLA spools")
                    InventoryStat(
                        value: String(format: "%.1f kg", inventory.totalGrams / 1000),
                        label: "Available material"
                    )
                    Spacer()
                }

                HStack(spacing: 4) {
                    ForEach(Array(inventory.spools.prefix(18))) { spool in
                        RoundedRectangle(cornerRadius: 3, style: .continuous)
                            .fill(Color(hex: spool.color))
                            .frame(height: 13)
                    }
                    if inventory.spools.count > 18 {
                        Text("+\(inventory.spools.count - 18)")
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(.white.opacity(0.45))
                            .padding(.leading, 4)
                    }
                }

                Text(sourceFootnote)
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.48))
            } else {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Reading Bambu Studio Beta inventory...")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.55))
                }
            }
        }
        .padding(17)
        .background(CardSurface())
    }

    private var sourceFootnote: String {
        switch store.paletteSource {
        case .inventory:
            return "Physical colors are selected only from this stock. Recipes show maximum available material before slicing."
        case .catalog:
            return "Catalog mode can use colors not in stock. Switch to My Inventory for stock-safe selection and estimates."
        case .allBambu:
            return "Additional Bambu PLA families are included only when active in local inventory; catalog choices still need availability checks."
        case .custom:
            return "Custom brand libraries are local JSON data; verify printer profiles and physical colors before printing."
        case .exactCMYKW:
            return "Exact CMYKW uses true anchor colors. Load matching physical filaments before printing."
        }
    }
}

private struct InventoryStat: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.headline.monospacedDigit())
                .foregroundStyle(.white.opacity(0.9))
            Text(label)
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.48))
        }
    }
}
