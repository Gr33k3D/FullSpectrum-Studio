import Foundation

enum PaletteMode: String, CaseIterable, Identifiable {
    case official
    case cmykw

    var id: Self { self }

    var title: String {
        switch self {
        case .official: return "Bambu PLA"
        case .cmykw: return "CMYKW"
        }
    }

    var explanation: String {
        switch self {
        case .official: return "Optimizes two to six physical anchor colors for the source model."
        case .cmykw: return "Assigns cyan, magenta, yellow, black, white and warm-white roles."
        }
    }
}

enum PaletteSource: String, CaseIterable, Identifiable {
    case inventory
    case catalog
    case allBambu = "all-bambu"
    case custom
    case exactCMYKW = "exact-cmykw"

    var id: Self { self }

    var title: String {
        switch self {
        case .inventory: return "My Inventory"
        case .catalog: return "Bambu Core"
        case .allBambu: return "All Bambu"
        case .custom: return "Custom Brands"
        case .exactCMYKW: return "Exact CMYKW"
        }
    }

    var explanation: String {
        switch self {
        case .inventory: return "Only choose colors listed in your Bambu Studio Beta inventory."
        case .catalog: return "Plan with supported PLA Basic, Matte and Silk+ colors for the selected planning region."
        case .allBambu: return "Core Bambu palette plus other active Bambu PLA types detected in your inventory."
        case .custom: return "Choose colors from a local JSON filament library."
        case .exactCMYKW: return "Use literal cyan, magenta, yellow, black and whites. Load matching physical colors."
        }
    }
}

enum CatalogRegion: String, CaseIterable, Identifiable {
    case global
    case europe = "eu"
    case northAmerica = "us-ca"
    case unitedKingdom = "uk"
    case australiaNewZealand = "au-nz"
    case asia

    var id: Self { self }

    var title: String {
        switch self {
        case .global: return "Global"
        case .europe: return "Europe"
        case .northAmerica: return "US / Canada"
        case .unitedKingdom: return "United Kingdom"
        case .australiaNewZealand: return "Australia / NZ"
        case .asia: return "Asia"
        }
    }
}

enum RealSlotSelection: String, CaseIterable, Identifiable {
    case auto
    case two = "2"
    case three = "3"
    case four = "4"
    case five = "5"
    case six = "6"
    case seven = "7"
    case eight = "8"

    var id: Self { self }
    var title: String {
        switch self {
        case .auto: return "Auto 2-6"
        case .seven: return "7 exp"
        case .eight: return "8 exp"
        default: return rawValue
        }
    }
}

enum PlannerMode: String, CaseIterable, Identifiable {
    case best
    case fast

    var id: Self { self }

    var title: String {
        switch self {
        case .best: return "Best"
        case .fast: return "Fast"
        }
    }

    var explanation: String {
        switch self {
        case .best:
            return "Deep search with wider anchor beams, swap refinement, and dense 2/3-color Bambu mix ratios. Can take minutes on complex files."
        case .fast:
            return "Uses the previous quicker anchor planner and smaller ratio set for fast previews or troubleshooting."
        }
    }
}

enum PlanningSample: String, CaseIterable, Identifiable {
    case paint = "paint"
    case preview = "preview"

    var id: Self { self }

    var title: String {
        switch self {
        case .paint: return "Paint states"
        case .preview: return "Render preview"
        }
    }

    var explanation: String {
        switch self {
        case .paint:
            return "Weights planning from the original Bambu paint-state counts."
        case .preview:
            return "Weights planning from the optimized render preview, then exports by exact original paint states."
        }
    }
}

enum MixPrediction: String, CaseIterable, Identifiable {
    case bambu

    var id: Self { self }
    var title: String { "Bambu Studio Reconstruction" }
    var explanation: String { "Mixed swatches are computed from the same component recipes and rounded ratios Bambu loads." }
}

enum OutputApplication: String, CaseIterable, Identifiable {
    case bambuStudio = "bambu-studio"
    case orcaSlicer = "orca-slicer"

    var id: Self { self }

    var title: String {
        switch self {
        case .bambuStudio: return "Bambu Studio"
        case .orcaSlicer: return "OrcaSlicer"
        }
    }
}

enum PreviewMode: String, CaseIterable, Identifiable {
    case plateImage = "Plate render"
    case original = "Original"
    case predicted = "Reduced / predicted"
    case validation = "Validation"
    case colorLoss = "Heatmap"
    case anchorInfluence = "Anchor influence"
    case wireframe = "Wireframe"

    var id: Self { self }
}

enum ViewerPerformance: String, CaseIterable, Identifiable {
    case fast = "Fast"
    case balanced = "Balanced"
    case high = "High"
    case maximum = "Maximum"

    var id: Self { self }
}

struct InventorySnapshot: Decodable {
    let source: String?
    let allCount: Int
    let usableCount: Int
    let totalGrams: Double
    let catalog: CatalogSnapshot?
    let anchorOptions: [AnchorCandidate]?
    let spools: [InventorySpool]
}

struct CatalogSnapshot: Decodable {
    let source: String?
    let bambuStudio: BambuStudioInstallSnapshot?
    let totalRows: Int
    let coreUsableCount: Int
    let allUsableCount: Int
    let families: [CatalogFamilyCount]
}

struct BambuStudioInstallSnapshot: Decodable {
    let version: String?
    let build: String?
    let path: String?
}

struct CatalogFamilyCount: Decodable, Identifiable {
    let series: String
    let count: Int

    var id: String { series }
}

struct InventorySpool: Decodable, Identifiable {
    let name: String
    let series: String
    let brand: String
    let color: String
    let preset: String
    let filamentID: String
    let remainingGrams: Double
    let initialGrams: Double

    var id: String { "\(series)-\(color)-\(remainingGrams)" }
}

struct AnchorCandidate: Decodable, Identifiable, Hashable {
    let key: String
    let name: String
    let series: String
    let brand: String
    let color: String
    let preset: String
    let filamentID: String
    let remainingGrams: Double?
    let availability: String?
    let catalogSource: String?

    var id: String { key }
}

struct ProjectInspection: Decodable {
    let input: String
    let filename: String
    let sourceSlots: Int
    let sourceColors: [String]
    let thumbnail: String?
    let previewMesh: String?
    let previewNotice: String?
    let metrics: MeshMetrics?
    let `import`: ImportSummary?
}

struct MeshMetrics: Decodable {
    let objectCount: Int
    let vertexCount: Int
    let triangleCount: Int
    let polygonCount: Int
    let textureBytes: Int
    let recommendedRenderMode: String
    let previewMemoryEstimateBytes: Int
    let previewBuildEstimateSeconds: Double
}

struct ConversionResult: Decodable {
    let input: String
    let output: String
    let csv: String
    let report: String
    let colorValidationReport: String
    let mode: String
    let paletteSource: String
    let plannerMode: String?
    let planningSample: String?
    let catalogRegion: String?
    let catalogRegionLabel: String?
    let catalogSource: String?
    let materialFamilies: [String]?
    let pinnedAnchorKeys: [String]?
    let sourceSlots: Int
    let realSlots: Int
    let outputSlots: Int
    let qualityBias: Int?
    let qualityBiasMode: String?
    let validation: String
    let paintedSlots: [Int]
    let outputColors: [String]?
    let worstMatch: WorstColorMatch?
    let inventory: InventorySnapshot
    let anchors: [AnchorFilament]
    let recipes: [RecipeItem]
    let quality: QualityMetrics
    let colorValidation: ColorValidationSummary
    let printability: PrintabilityMetrics
    let preservation: PreservationResult
    let reference: ReferenceSummary?
    let analysisAssets: AnalysisAssets?
    let `import`: ImportSummary?
    let recommendation: AnchorRecommendation?
    let warnings: [String]

    var mixedRecipes: [RecipeItem] {
        recipes.filter { $0.kind == "MIX" }
    }
}

struct PlanPreviewResult: Decodable {
    let type: String
    let input: String
    let filename: String
    let mode: String
    let paletteSource: String
    let plannerMode: String
    let planningSample: String
    let catalogRegion: String?
    let catalogRegionLabel: String?
    let catalogSource: String?
    let materialFamilies: [String]?
    let pinnedAnchorKeys: [String]?
    let sourceSlots: Int
    let realSlots: Int
    let outputSlots: Int
    let qualityBias: Int
    let qualityBiasMode: String
    let outputColors: [String]?
    let analysisAssets: AnalysisAssets?
    let worstMatch: WorstColorMatch?
    let anchors: [AnchorFilament]
    let recipes: [RecipeItem]
    let quality: QualityMetrics
    let printability: PrintabilityMetrics
    let recommendation: AnchorRecommendation?
    let reference: ReferenceSummary?
    let `import`: ImportSummary?
    let warnings: [String]

    var mixedRecipes: [RecipeItem] {
        recipes.filter { $0.kind == "MIX" }
    }
}

struct ColorValidationSummary: Decodable {
    let predictionModel: String
    let verified: Bool
    let maximumDeltaE: Double
    let recipes: [ColorValidationItem]
}

struct ColorValidationItem: Decodable, Identifiable {
    let oldSlot: Int
    let newSlot: Int
    let target: String
    let appPrediction: String
    let exported: String
    let bambuLoaded: String
    let targetDeltaE: Double
    let predictionDeltaE: Double
    let components: String
    let ratios: String

    var id: Int { oldSlot }
}

struct QualityMetrics: Decodable {
    let estimatedDeltaE: Double
    let maximumDeltaE: Double
    let qualityScore: Double
    let referenceSimilarityScore: Double?
    let referenceEstimatedDeltaE: Double?
    let confidenceScore: Double
    let confidenceLabel: String
    let brightnessError: Double?
    let contrastRetention: Double?
    let mixModel: String
    let resolvedQualityBias: Int?
    let qualityBiasMode: String?
    let plannerMode: String?
    let planningSample: String?
}

struct PrintabilityMetrics: Decodable {
    let physicalSlots: Int
    let mixedSlots: Int
    let paintedMixedShare: Double
    let purgeTransitionMean: Double?
    let difficulty: String
    let swapRisk: String
    let filamentUsageEstimate: Double?
    let printTimeEstimate: Double?
    let sliceRequiredForTimeAndUsage: Bool
    let recommendations: [String]
}

struct PreservationResult: Decodable {
    let geometryPreserved: Bool
    let textureResourcesPreserved: Bool
    let checkedMembers: Int
    let paintRemapVerified: Bool
}

struct AnalysisAssets: Decodable {
    let predictedMesh: String?
    let heatmapMesh: String?
    let anchorInfluenceMesh: String?
}

struct WorstColorMatch: Decodable {
    let sourceSlot: Int
    let targetColor: String
    let predictedColor: String
    let deltaE: Double
    let paintedShare: Double
    let severity: String
    let suggestedFilament: SuggestedFilament?
}

struct SuggestedFilament: Decodable {
    let key: String?
    let name: String
    let series: String?
    let color: String
    let estimatedDeltaE: Double
    let availability: String
}

struct ImportSummary: Decodable {
    let sourceType: String
    let texture: String
    let vertexCount: Int
    let triangleCount: Int
    let internalColorCount: Int
    let exportColorCount: Int
    let compressedForBambu: Bool
}

struct AnchorRecommendation: Decodable {
    let key: String?
    let name: String
    let series: String?
    let color: String
    let estimatedDeltaEReduction: Double
    let estimatedQualityScore: Double
    let estimatedMixedSlots: Int
    let availability: String
}

struct ReferenceSummary: Decodable {
    let filename: String
    let kind: String
    let hasTexture: Bool
    let dominantColors: [ReferenceColor]
}

struct ReferenceColor: Decodable, Identifiable {
    let color: String
    let weight: Double
    var id: String { color }
}

struct AnchorFilament: Decodable, Identifiable {
    let key: String?
    let slot: Int
    let name: String
    let series: String?
    let color: String
    let preset: String
    let filamentID: String
    let remainingGrams: Double?

    var id: String { key ?? "\(slot)-\(name)-\(color)" }
}

struct RecipeItem: Decodable, Identifiable {
    let oldSlot: Int
    let newSlot: Int
    let targetColor: String
    let kind: String
    let label: String
    let components: String
    let ratios: String
    let preview: String
    let deltaE: Double
    let directDeltaE: Double
    let visualGain: Double
    let availableGrams: Double?

    var id: Int { oldSlot }
}

struct ConversionProgress: Decodable {
    let progress: Double
    let message: String
}
