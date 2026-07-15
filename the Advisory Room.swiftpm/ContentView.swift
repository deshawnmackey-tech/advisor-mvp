import SwiftUI

// ── Models ────────────────────────────────────────────────────────────────────

enum Scenario: String, CaseIterable, Identifiable {
    case sale     = "sale"
    case loan     = "loan"
    case investor = "investor"
    var id: String { rawValue }

    var title: String {
        switch self {
        case .sale:     return "Sale Readiness"
        case .loan:     return "SBA Loan"
        case .investor: return "Investor"
        }
    }

    var icon: String {
        switch self {
        case .sale:     return "building.2"
        case .loan:     return "banknote"
        case .investor: return "chart.line.uptrend.xyaxis"
        }
    }

    var description: String {
        switch self {
        case .sale:     return "Am I ready to sell my business?"
        case .loan:     return "Can I qualify for an SBA 7(a) loan?"
        case .investor: return "What should I include in my pitch deck?"
        }
    }

    var accentColor: Color {
        switch self {
        case .sale:     return Color(red: 0.18, green: 0.52, blue: 0.89)
        case .loan:     return Color(red: 0.13, green: 0.69, blue: 0.53)
        case .investor: return Color(red: 0.58, green: 0.33, blue: 0.87)
        }
    }
}

struct AdviseRequest: Encodable {
    let client_id: String
    let scenario: String
    let message: String
    let rehearsal: Bool
}

struct AdviseResponse: Decodable {
    let payload: PayloadWrapper
    let trace_id: String
}

struct PayloadWrapper: Decodable {
    let snapshot: AnyCodable?
    let actions: [String]?
    let disclaimer: String?
}

// AnyCodable — lightweight decode for arbitrary JSON
struct AnyCodable: Decodable {
    let value: Any
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let v = try? container.decode([String: AnyCodableValue].self) {
            value = v
        } else if let v = try? container.decode([AnyCodableValue].self) {
            value = v
        } else {
            value = [String: String]()
        }
    }

    var displayPairs: [(String, String)] {
        guard let dict = value as? [String: AnyCodableValue] else { return [] }
        return dict.compactMap { k, v in
            guard let s = v.stringValue else { return nil }
            return (k.replacingOccurrences(of: "_", with: " ").capitalized, s)
        }.sorted { $0.0 < $1.0 }
    }
}

struct AnyCodableValue: Decodable {
    let stringValue: String?
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let d = try? c.decode(Double.self) {
            stringValue = formatNumber(d)
        } else if let i = try? c.decode(Int.self) {
            stringValue = formatNumber(Double(i))
        } else if let b = try? c.decode(Bool.self) {
            stringValue = b ? "Yes" : "No"
        } else if let s = try? c.decode(String.self) {
            stringValue = s
        } else {
            stringValue = nil
        }
    }
}

private func formatNumber(_ n: Double) -> String {
    if n >= 1_000_000 { return String(format: "$%.2fM", n / 1_000_000) }
    if n >= 1_000     { return String(format: "$%.0fK", n / 1_000) }
    if n < 10 && n > -10 { return String(format: "%.2f", n) }
    return String(format: "%.0f", n)
}

// ── Network Layer ─────────────────────────────────────────────────────────────

enum APIError: LocalizedError {
    case noServer
    case badStatus(Int)
    case decodingFailed(String)
    var errorDescription: String? {
        switch self {
        case .noServer:         return "Cannot reach the advisory server. Is it running on :8000?"
        case .badStatus(let c): return "Server returned status \(c)."
        case .decodingFailed(let m): return "Response error: \(m)"
        }
    }
}

@MainActor
class AdvisoryAPI: ObservableObject {
    // Change this to your production URL before shipping
    static let baseURL = "http://localhost:8000"

    func advise(scenario: Scenario, clientID: String, message: String) async throws -> AdviseResponse {
        guard let url = URL(string: "\(Self.baseURL)/v1/advise") else { throw APIError.noServer }
        var req = URLRequest(url: url, timeoutInterval: 90)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(
            AdviseRequest(client_id: clientID, scenario: scenario.rawValue, message: message, rehearsal: false)
        )
        let (data, resp) = try await URLSession.shared.data(for: req)
        if let http = resp as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw APIError.badStatus(http.statusCode)
        }
        do {
            return try JSONDecoder().decode(AdviseResponse.self, from: data)
        } catch {
            throw APIError.decodingFailed(error.localizedDescription)
        }
    }
}

// ── View Model ────────────────────────────────────────────────────────────────

@MainActor
class ReportViewModel: ObservableObject {
    @Published var isLoading = false
    @Published var result: AdviseResponse?
    @Published var errorMessage: String?
    @Published var selectedScenario: Scenario = .sale
    @Published var clientID: String = "demo_client"

    private let api = AdvisoryAPI()

    func run() {
        guard !isLoading else { return }
        isLoading = true
        result = nil
        errorMessage = nil
        Task {
            do {
                let res = try await api.advise(
                    scenario: selectedScenario,
                    clientID: clientID,
                    message: selectedScenario.description
                )
                self.result = res
            } catch {
                self.errorMessage = error.localizedDescription
            }
            self.isLoading = false
        }
    }
}

// ── Views ─────────────────────────────────────────────────────────────────────

struct ContentView: View {
    @StateObject private var vm = ReportViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    HeaderView()
                    ClientIDField(clientID: $vm.clientID)
                    ScenarioPicker(selected: $vm.selectedScenario)
                    RunButton(isLoading: vm.isLoading, accent: vm.selectedScenario.accentColor) {
                        vm.run()
                    }
                    if let err = vm.errorMessage {
                        ErrorCard(message: err)
                    }
                    if let result = vm.result {
                        ResultCard(response: result, accent: vm.selectedScenario.accentColor)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 40)
            }
            .background(Color(.systemGroupedBackground).ignoresSafeArea())
            .navigationBarHidden(true)
        }
    }
}

struct HeaderView: View {
    var body: some View {
        VStack(spacing: 4) {
            HStack {
                Image(systemName: "building.columns.fill")
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundColor(.indigo)
                Text("The Advisory Room")
                    .font(.system(size: 26, weight: .bold, design: .rounded))
            }
            Text("AI-Powered Business Readiness")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding(.top, 20)
    }
}

struct ClientIDField: View {
    @Binding var clientID: String
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Client ID", systemImage: "person.circle")
                .font(.caption.weight(.semibold))
                .foregroundColor(.secondary)
            TextField("demo_client", text: $clientID)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .padding(12)
                .background(Color(.secondarySystemGroupedBackground))
                .cornerRadius(12)
        }
    }
}

struct ScenarioPicker: View {
    @Binding var selected: Scenario
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Advisory Lens")
                .font(.caption.weight(.semibold))
                .foregroundColor(.secondary)
            HStack(spacing: 10) {
                ForEach(Scenario.allCases) { s in
                    ScenarioChip(scenario: s, isSelected: selected == s) {
                        withAnimation(.spring(response: 0.3)) { selected = s }
                    }
                }
            }
        }
    }
}

struct ScenarioChip: View {
    let scenario: Scenario
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: 4) {
                Image(systemName: scenario.icon)
                    .font(.system(size: 18, weight: .medium))
                Text(scenario.title)
                    .font(.caption.weight(.semibold))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .foregroundColor(isSelected ? .white : scenario.accentColor)
            .background(
                isSelected
                    ? scenario.accentColor
                    : scenario.accentColor.opacity(0.1)
            )
            .cornerRadius(14)
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(scenario.accentColor.opacity(isSelected ? 0 : 0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

struct RunButton: View {
    let isLoading: Bool
    let accent: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(.white)
                        .scaleEffect(0.85)
                } else {
                    Image(systemName: "bolt.fill")
                }
                Text(isLoading ? "Analyzing…" : "Run Advisory Report")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .foregroundColor(.white)
            .background(isLoading ? accent.opacity(0.6) : accent)
            .cornerRadius(16)
        }
        .disabled(isLoading)
        .buttonStyle(.plain)
        .animation(.easeInOut(duration: 0.2), value: isLoading)
    }
}

struct ErrorCard: View {
    let message: String
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.orange)
                .font(.title3)
            Text(message)
                .font(.subheadline)
                .foregroundColor(.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.1))
        .cornerRadius(14)
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(Color.orange.opacity(0.3), lineWidth: 1)
        )
    }
}

struct ResultCard: View {
    let response: AdviseResponse
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack {
                Image(systemName: "checkmark.seal.fill")
                    .foregroundColor(accent)
                Text("Advisory Report")
                    .font(.headline)
                Spacer()
                Text(String(response.trace_id.prefix(8)))
                    .font(.caption2.monospaced())
                    .foregroundColor(.secondary)
            }
            .padding(16)

            Divider()

            // Snapshot metrics
            if let pairs = response.payload.snapshot?.displayPairs, !pairs.isEmpty {
                VStack(alignment: .leading, spacing: 0) {
                    SectionHeader(title: "Financial Snapshot", icon: "chart.bar.fill")
                    ForEach(pairs, id: \.0) { key, value in
                        MetricRow(label: key, value: value, accent: accent)
                    }
                }
            }

            // Actions
            if let actions = response.payload.actions, !actions.isEmpty {
                Divider().padding(.horizontal, 16)
                VStack(alignment: .leading, spacing: 0) {
                    SectionHeader(title: "Recommended Actions", icon: "list.bullet.clipboard.fill")
                    ForEach(Array(actions.enumerated()), id: \.offset) { i, action in
                        ActionRow(number: i + 1, text: action, accent: accent)
                    }
                }
            }

            // Disclaimer
            if let disclaimer = response.payload.disclaimer {
                Divider().padding(.horizontal, 16)
                Text(disclaimer)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(16)
            }
        }
        .background(Color(.secondarySystemGroupedBackground))
        .cornerRadius(18)
        .shadow(color: Color.black.opacity(0.06), radius: 12, x: 0, y: 4)
    }
}

struct SectionHeader: View {
    let title: String
    let icon: String
    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.caption.weight(.semibold))
            Text(title)
                .font(.caption.weight(.semibold))
        }
        .foregroundColor(.secondary)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }
}

struct MetricRow: View {
    let label: String
    let value: String
    let accent: Color
    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline.weight(.semibold))
                .foregroundColor(.primary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.clear)
    }
}

struct ActionRow: View {
    let number: Int
    let text: String
    let accent: Color
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Text("\(number)")
                .font(.caption.weight(.bold))
                .foregroundColor(.white)
                .frame(width: 22, height: 22)
                .background(accent)
                .clipShape(Circle())
            Text(text)
                .font(.subheadline)
                .foregroundColor(.primary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }
}
