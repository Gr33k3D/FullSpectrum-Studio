import SwiftUI

extension Color {
    init(hex: String) {
        let value = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var rgb: UInt64 = 0
        Scanner(string: value).scanHexInt64(&rgb)
        let red, green, blue: Double
        switch value.count {
        case 6:
            red = Double((rgb >> 16) & 0xFF) / 255
            green = Double((rgb >> 8) & 0xFF) / 255
            blue = Double(rgb & 0xFF) / 255
        default:
            red = 0.35
            green = 0.4
            blue = 0.45
        }
        self.init(.sRGB, red: red, green: green, blue: blue, opacity: 1)
    }
}
