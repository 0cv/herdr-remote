import Foundation
import Network
import Observation

enum ConnectionState: Equatable {
    case disconnected
    case connecting
    case connected
    case reconnecting(attempt: Int)
}

@Observable
final class RelayConnection {
    var agents: [Agent] = []
    var connectionState: ConnectionState = .disconnected
    var hostAddress: String = ""
    var paneHistory: [String: String] = [:]

    var isConnected: Bool { connectionState == .connected }

    private var task: URLSessionWebSocketTask?
    private var pathMonitor: NWPathMonitor?
    private let session = URLSession(configuration: .default)
    private var reconnectAttempt = 0
    private var reconnectTask: Task<Void, Never>?

    init() {
        startPathMonitor()
    }

    deinit {
        pathMonitor?.cancel()
    }

    // MARK: - Network Path Monitor

    private func startPathMonitor() {
        pathMonitor = NWPathMonitor()
        pathMonitor?.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            DispatchQueue.main.async {
                if path.status == .satisfied, !self.isConnected, !self.hostAddress.isEmpty {
                    self.connect(to: self.hostAddress)
                }
            }
        }
        pathMonitor?.start(queue: .global(qos: .utility))
    }

    // MARK: - WebSocket

    func connect(to urlString: String) {
        guard let url = URL(string: urlString) else { return }
        hostAddress = urlString
        reconnectTask?.cancel()
        task?.cancel()
        connectionState = .connecting
        task = session.webSocketTask(with: url)
        task?.resume()
        connectionState = .connected
        reconnectAttempt = 0
        listen()
    }

    func disconnect() {
        reconnectTask?.cancel()
        task?.cancel(with: .normalClosure, reason: nil)
        connectionState = .disconnected
    }

    func send(response: ResponseMessage) {
        guard let data = try? JSONEncoder().encode(response) else { return }
        task?.send(.string(String(data: data, encoding: .utf8)!)) { _ in }
    }

    func fetchHistory(for paneId: String) {
        let msg = ["type": "read_pane", "pane_id": paneId]
        guard let data = try? JSONSerialization.data(withJSONObject: msg) else { return }
        task?.send(.string(String(data: data, encoding: .utf8)!)) { _ in }
    }

    private func listen() {
        task?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    self?.handle(text)
                case .data(let data):
                    self?.handle(String(data: data, encoding: .utf8) ?? "")
                @unknown default:
                    break
                }
                self?.listen()
            case .failure:
                DispatchQueue.main.async {
                    self?.scheduleReconnect()
                }
            }
        }
    }

    private func scheduleReconnect() {
        guard !hostAddress.isEmpty else {
            connectionState = .disconnected
            return
        }
        reconnectAttempt += 1
        connectionState = .reconnecting(attempt: reconnectAttempt)
        let delay = min(Double(1 << min(reconnectAttempt, 5)), 30.0) // 1, 2, 4, 8, 16, 30 cap
        reconnectTask = Task { @MainActor in
            try? await Task.sleep(for: .seconds(delay))
            guard !Task.isCancelled else { return }
            connect(to: hostAddress)
        }
    }

    private func handle(_ text: String) {
        guard let data = text.data(using: .utf8),
              let msg = try? JSONDecoder().decode(AgentMessage.self, from: data) else { return }

        DispatchQueue.main.async { [self] in
            switch msg.type {
            case "agents":
                guard let list = msg.agents else { return }
                for a in list {
                    if let existing = agents.first(where: { $0.id == a.pane_id }) {
                        existing.status = AgentStatus(rawValue: a.status) ?? .unknown
                        existing.project = a.project
                        existing.host = a.host ?? "local"
                    } else {
                        agents.append(Agent(
                            id: a.pane_id, name: a.agent,
                            status: AgentStatus(rawValue: a.status) ?? .unknown,
                            project: a.project, cwd: a.cwd, host: a.host ?? "local"
                        ))
                    }
                }
                let activeIds = Set(list.map(\.pane_id))
                agents.removeAll { !activeIds.contains($0.id) }
                // Update live activity + widget
                let b = agents.filter { $0.status == .blocked }.count
                let w = agents.filter { $0.status == .working }.count
                let i = agents.filter { $0.status == .idle || $0.status == .unknown }.count
                LiveActivityManager.shared.update(blocked: b, working: w, idle: i)
                let defaults = UserDefaults(suiteName: "group.com.dcolinmorgan.herdi")
                defaults?.set(b, forKey: "blocked_count")
                defaults?.set(w, forKey: "working_count")
                defaults?.set(i, forKey: "idle_count")

            case "blocked":
                if let pid = msg.pane_id,
                   let agent = agents.first(where: { $0.id == pid }) {
                    agent.prompt = msg.prompt
                    agent.options = msg.options
                    agent.status = .blocked
                    HapticManager.shared.blocked()
                    NotificationManager.shared.notifyBlocked(agent: agent.name, project: agent.project)
                }

            case "pane_content":
                if let pid = msg.pane_id, let content = msg.prompt {
                    paneHistory[pid] = content
                }

            default:
                break
            }
        }
    }
}
