import Cocoa
import WebKit
import Darwin

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var serverProcess: Process?
    private var serverPort: UInt16 = 8085
    private var didLoadInitialPage = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupMenu()
        setupWindow()

        let projectDir = resolveProjectDir()
        serverPort = findAvailablePort(preferred: 8085)
        startBackendServer(projectDir: projectDir, port: serverPort)
        waitForServerAndLoad(attempt: 0)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        stopBackendServer()
    }

    @objc private func reloadPage(_ sender: Any?) {
        webView?.reload()
    }

    private func setupMenu() {
        let mainMenu = NSMenu()

        let appMenuItem = NSMenuItem()
        mainMenu.addItem(appMenuItem)
        let appMenu = NSMenu()
        appMenu.addItem(NSMenuItem(title: "Garmin 2.0 Hakkında", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""))
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(NSMenuItem(title: "Çıkış", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        appMenuItem.submenu = appMenu

        let editMenuItem = NSMenuItem()
        mainMenu.addItem(editMenuItem)
        let editMenu = NSMenu(title: "Düzen")
        editMenu.addItem(NSMenuItem(title: "Geri Al", action: Selector(("undo:")), keyEquivalent: "z"))
        editMenu.addItem(NSMenuItem(title: "Kes", action: #selector(NSText.cut(_:)), keyEquivalent: "x"))
        editMenu.addItem(NSMenuItem(title: "Kopyala", action: #selector(NSText.copy(_:)), keyEquivalent: "c"))
        editMenu.addItem(NSMenuItem(title: "Yapıştır", action: #selector(NSText.paste(_:)), keyEquivalent: "v"))
        editMenu.addItem(NSMenuItem(title: "Tümünü Seç", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"))
        editMenuItem.submenu = editMenu

        let viewMenuItem = NSMenuItem()
        mainMenu.addItem(viewMenuItem)
        let viewMenu = NSMenu(title: "Görünüm")
        viewMenu.addItem(NSMenuItem(title: "Yenile", action: #selector(reloadPage(_:)), keyEquivalent: "r"))
        viewMenuItem.submenu = viewMenu

        NSApp.mainMenu = mainMenu
    }

    private func setupWindow() {
        let bgColor = NSColor(calibratedRed: 13.0 / 255.0, green: 19.0 / 255.0, blue: 15.0 / 255.0, alpha: 1.0)
        let screenFrame = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        window = NSWindow(
            contentRect: screenFrame,
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.minSize = NSSize(width: 980, height: 680)
        window.setFrame(screenFrame, display: true)
        window.title = "Garmin 2.0"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.isMovableByWindowBackground = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = bgColor
        window.isReleasedWhenClosed = false

        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        let macScript = WKUserScript(
            source: "document.documentElement.classList.add('macos-app');",
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        )
        config.userContentController.addUserScript(macScript)
        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")

        window.contentView?.addSubview(webView)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func resolveProjectDir() -> String {
        let serverPath = "/app/server.py"
        let fm = FileManager.default
        if let dir = Bundle.main.infoDictionary?["ProjectDir"] as? String,
           fm.fileExists(atPath: dir + serverPath) {
            return dir
        }
        // Prebuilt copies (e.g. the GitHub release zip) are not tied to the build machine:
        // remember the folder of the repository checkout the user picks once.
        let key = "ProjectDirOverride"
        if let saved = UserDefaults.standard.string(forKey: key),
           fm.fileExists(atPath: saved + serverPath) {
            return saved
        }
        let panel = NSOpenPanel()
        panel.title = "Garmin 2.0"
        panel.message = "Garmin analiz projesinin klasörünü seçin (app/server.py içeren klasör)"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        while panel.runModal() == .OK, let url = panel.url {
            if fm.fileExists(atPath: url.path + serverPath) {
                UserDefaults.standard.set(url.path, forKey: key)
                return url.path
            }
            showErrorAlert("Geçersiz klasör", message: "Seçilen klasörde app/server.py bulunamadı.")
        }
        return fm.currentDirectoryPath
    }

    private func isPortFree(_ port: UInt16) -> Bool {
        let sock = socket(AF_INET, SOCK_STREAM, 0)
        if sock < 0 { return false }
        defer { close(sock) }

        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = port.bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")

        let res = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return res == 0
    }

    private func findAvailablePort(preferred: UInt16) -> UInt16 {
        if isPortFree(preferred) { return preferred }
        for candidate in UInt16(8086)...UInt16(8120) {
            if isPortFree(candidate) { return candidate }
        }
        return preferred
    }

    private func resolvePythonPath() -> String {
        let candidates = [
            "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3"
        ]
        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            return path
        }
        return "/usr/bin/python3"
    }

    private func openServerLogHandle() -> FileHandle? {
        let fm = FileManager.default
        let logDir = fm.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/Garmin 2.0", isDirectory: true)
        let logURL = logDir.appendingPathComponent("server.log")
        do {
            try fm.createDirectory(at: logDir, withIntermediateDirectories: true)
            // Her açılışta log sıfırlanır; dosya sınırsız büyümez
            fm.createFile(atPath: logURL.path, contents: nil)
            return try FileHandle(forWritingTo: logURL)
        } catch {
            return FileHandle(forWritingAtPath: "/dev/null")
        }
    }

    private func startBackendServer(projectDir: String, port: UInt16) {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: resolvePythonPath())
        proc.arguments = ["app/server.py", String(port)]
        proc.currentDirectoryURL = URL(fileURLWithPath: projectDir)

        var env = ProcessInfo.processInfo.environment
        let basePath = env["PATH"] ?? "/usr/bin:/bin"
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:" + basePath
        env["PYTHONUNBUFFERED"] = "1"
        proc.environment = env

        // Sunucu çıktısı hata ayıklama için ~/Library/Logs/Garmin 2.0/server.log dosyasına yazılır
        let logHandle = openServerLogHandle()
        proc.standardOutput = logHandle
        proc.standardError = logHandle

        do {
            try proc.run()
            serverProcess = proc
        } catch {
            showErrorAlert("Sunucu Başlatılamadı", message: error.localizedDescription)
        }
    }

    private func stopBackendServer() {
        guard let proc = serverProcess, proc.isRunning else { return }
        proc.terminate()
        let deadline = Date().addingTimeInterval(2.0)
        while proc.isRunning && Date() < deadline {
            Thread.sleep(forTimeInterval: 0.05)
        }
        if proc.isRunning {
            kill(proc.processIdentifier, SIGKILL)
        }
        serverProcess = nil
    }

    private func waitForServerAndLoad(attempt: Int) {
        if didLoadInitialPage { return }
        guard let statusURL = URL(string: "http://127.0.0.1:\(serverPort)/api/status") else { return }

        var req = URLRequest(url: statusURL)
        req.timeoutInterval = 0.6

        URLSession.shared.dataTask(with: req) { [weak self] _, response, _ in
            guard let self = self else { return }
            if let http = response as? HTTPURLResponse, http.statusCode == 200 {
                DispatchQueue.main.async {
                    guard !self.didLoadInitialPage else { return }
                    self.didLoadInitialPage = true
                    if let appURL = URL(string: "http://127.0.0.1:\(self.serverPort)/") {
                        self.webView.load(URLRequest(url: appURL))
                    }
                }
                return
            }
            if attempt >= 80 {
                DispatchQueue.main.async {
                    self.showErrorAlert("Bağlantı Zaman Aşımı", message: "Yerel Garmin sunucusu 12 saniye içinde yanıt vermedi.")
                }
                return
            }
            DispatchQueue.global().asyncAfter(deadline: .now() + 0.15) {
                self.waitForServerAndLoad(attempt: attempt + 1)
            }
        }.resume()
    }

    private func showErrorAlert(_ title: String, message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = .critical
        alert.runModal()
        NSApp.terminate(nil)
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
