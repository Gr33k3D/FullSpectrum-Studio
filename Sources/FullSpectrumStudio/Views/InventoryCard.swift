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
                TextField("Search owned filament names or colors", text: $store.inventorySearch)
                    .textFieldStyle(.roundedBorder)
                    .font(.caption)
                HStack(spacing: 20) {
                    InventoryStat(value: "\(inventory.usableCount)", label: "Active PLA spools")
                    InventoryStat(
                        value: String(format: "%.1f kg", inventory.totalGrams / 1000),
                        label: "Available material"
                    )
                    Spacer()
                }

                HStack(spacing: 4) {
                    ForEach(Array(filteredSpools(inventory).prefix(18))) { spool in
                        RoundedRectangle(cornerRadius: 3, style: .continuous)
                            .fill(Color(hex: spool.color))
                            .frame(height: 13)
                    }
                    if filteredSpools(inventory).count > 18 {
                        Text("+\(filteredSpools(inventory).count - 18)")
                            .font(.caption2.monospacedDigit())
                            .foregroundStyle(.white.opacity(0.45))
                            .padding(.leading, 4)
                    }
                }

                ForEach(Array(filteredSpools(inventory).prefix(3))) { spool in
                    HStack(spacing: 7) {
                        Circle().fill(Color(hex: spool.color)).frame(width: 10, height: 10)
                        Text(spool.name)
                        Spacer()
                        Text("\(Int(spool.remainingGrams)) g owned")
                            .monospacedDigit()
                    }
                    .font(.caption2)
                    .foregroundStyle(.white.opacity(0.62))
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

    private func filteredSpools(_ inventory: InventorySnapshot) -> [InventorySpool] {
        guard !store.inventorySearch.isEmpty else { return inventory.spools }
        return inventory.spools.filter {
            $0.name.localizedCaseInsensitiveContains(store.inventorySearch)
            || $0.color.localizedCaseInsensitiveContains(store.inventorySearch)
            || $0.brand.localizedCaseInsensitiveContains(store.inventorySearch)
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
