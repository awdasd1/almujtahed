import Cocoa
import WebKit
import CoreText
import Darwin

final class AppDownloads: NSObject, WKDownloadDelegate {
    static let shared = AppDownloads()
    private var owners: [ObjectIdentifier: AnyObject] = [:]

    func hold(_ owner: AnyObject) {
        owners[ObjectIdentifier(owner)] = owner
    }

    func adopt(_ download: WKDownload, owner: AnyObject) {
        download.delegate = self
        owners[ObjectIdentifier(download)] = owner
        owners.removeValue(forKey: ObjectIdentifier(owner))
    }

    private func release(_ download: WKDownload) {
        owners.removeValue(forKey: ObjectIdentifier(download))
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let folder = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Downloads")
        var name = suggestedFilename.trimmingCharacters(in: .whitespacesAndNewlines)
        if name.isEmpty || name == "Unknown" || name == "unknown" {
            name = "تصدير-المجتهد.txt"
        }
        let base = (name as NSString).deletingPathExtension
        let ext = (name as NSString).pathExtension
        var dest = folder.appendingPathComponent(name)
        var index = 2
        while FileManager.default.fileExists(atPath: dest.path) {
            dest = folder.appendingPathComponent(ext.isEmpty ? "\(base)-\(index)" : "\(base)-\(index).\(ext)")
            index += 1
        }
        completionHandler(dest)
    }

    func downloadDidFinish(_ download: WKDownload) {
        release(download)
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        release(download)
    }
}

final class HiddenDownloadView: NSObject, WKNavigationDelegate {
    let webView: WKWebView

    init(configuration: WKWebViewConfiguration) {
        webView = WKWebView(frame: .zero, configuration: configuration)
        super.init()
        webView.navigationDelegate = self
        AppDownloads.shared.hold(self)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        decisionHandler(.download)
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        AppDownloads.shared.adopt(download, owner: self)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(.download)
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        AppDownloads.shared.adopt(download, owner: self)
    }
}

private func navigationWantsDownload(_ action: WKNavigationAction) -> Bool {
    if action.shouldPerformDownload { return true }
    let scheme = action.request.url?.scheme?.lowercased() ?? ""
    return scheme == "blob" || scheme == "data"
}

private func responseWantsDownload(_ response: WKNavigationResponse) -> Bool {
    let mime = (response.response.mimeType ?? "").lowercased()
    if mime.isEmpty || mime == "text/html" || mime == "application/xhtml+xml" { return false }
    if !response.canShowMIMEType { return true }
    return mime == "text/csv" || mime == "application/json" || mime == "application/octet-stream"
        || mime == "text/tab-separated-values" || mime == "application/pdf"
}

func presentWebOpenPanel(on window: NSWindow, parameters: WKOpenPanelParameters, completionHandler: @escaping ([URL]?) -> Void) {
    let panel = NSOpenPanel()
    panel.canChooseFiles = true
    panel.canChooseDirectories = parameters.allowsDirectories
    panel.allowsMultipleSelection = parameters.allowsMultipleSelection
    panel.resolvesAliases = true
    panel.prompt = "اختيار"
    NSApp.activate(ignoringOtherApps: true)
    panel.beginSheetModal(for: window) { response in
        completionHandler(response == .OK ? panel.urls : nil)
    }
}

final class ReadingWindow: NSObject, NSWindowDelegate, WKUIDelegate, WKNavigationDelegate {
    let window: NSWindow
    let webView: WKWebView
    var onClose: (() -> Void)?
    var openPopup: ((WKWebViewConfiguration, WKNavigationAction) -> WKWebView?)?

    init(configuration: WKWebViewConfiguration) {
        webView = WKWebView(frame: .zero, configuration: configuration)
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1200, height: 800)
        let margin: CGFloat = 24
        let height = max(680, screen.height - margin * 2)
        let width = min(max(480, height * 210 / 297 * 2), screen.width - margin * 2)
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: width, height: height),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "قراءة"
        window.minSize = NSSize(width: 480, height: 680)
        window.contentView = webView
        window.isReleasedWhenClosed = false
        super.init()
        window.delegate = self
        webView.uiDelegate = self
        webView.navigationDelegate = self
        window.center()
    }

    func show() {
        window.makeKeyAndOrderFront(nil)
    }

    func windowWillClose(_ notification: Notification) {
        let callback = onClose
        onClose = nil
        DispatchQueue.main.async { callback?() }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        openPopup?(configuration, navigationAction)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if navigationWantsDownload(navigationAction) {
            decisionHandler(.download)
            return
        }
        if navigationAction.navigationType == .linkActivated,
           let url = navigationAction.request.url,
           let host = url.host,
           host != "localhost", host != "127.0.0.1" {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        AppDownloads.shared.adopt(download, owner: self)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(responseWantsDownload(navigationResponse) ? .download : .allow)
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        AppDownloads.shared.adopt(download, owner: self)
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        presentWebOpenPanel(on: window, parameters: parameters, completionHandler: completionHandler)
    }
}

/* طباعة أصلية للماك: WKWebView يتجاهل window.print() من الجافاسكربت،
   فتستلم هذه الطابعة الدائمة (لا تُدمَّر طوال حياة التطبيق) HTML الورقة
   المقسّمة، وتحملها في عرض ويب خفي خارج الشاشة، وتنتظر اكتمال تقسيم
   الصفحات (__pagedDone)، ثم تفتح لوحة طباعة نظام التشغيل
   (NSPrintPanel) على نافذة التطبيق. عملية الطباعة نفسها محفوظة بقوة
   حتى اكتمالها — تحريرها مبكرًا كان يمنع ظهور اللوحة ويسبب انهيارًا */
final class NativePrinter: NSObject, WKNavigationDelegate {
    static let shared = NativePrinter()

    private let webView: WKWebView
    private let hostWindow: NSWindow
    private weak var presentingWindow: NSWindow?
    private var pollTimer: Timer?
    private var startedAt = Date()
    private var phase: Phase = .idle
    private var currentOperation: NSPrintOperation?
    private var queue: [(html: String, baseURL: URL, presenting: NSWindow?)] = []

    private enum Phase { case idle, loading, panel }

    override init() {
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 900, height: 1200), configuration: configuration)
        hostWindow = NSWindow(
            contentRect: NSRect(x: -12000, y: -12000, width: 900, height: 1200),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        hostWindow.contentView = webView
        super.init()
        webView.navigationDelegate = self
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        NSLog("AlMujtahedPrint: navigation finished")
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        NSLog("AlMujtahedPrint: navigation failed: %@", error.localizedDescription)
    }

    func enqueue(html: String, baseURL: URL, presentingWindow: NSWindow?) {
        NSLog("AlMujtahedPrint: enqueue %d chars", html.count)
        queue.append((html: html, baseURL: baseURL, presenting: presentingWindow))
        pump()
    }

    private func pump() {
        guard phase == .idle, !queue.isEmpty else { return }
        let job = queue.removeFirst()
        phase = .loading
        presentingWindow = job.presenting
        startedAt = Date()
        hostWindow.orderFrontRegardless()
        webView.loadHTMLString(job.html, baseURL: job.baseURL)
        pollTimer?.invalidate()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            self?.poll()
        }
    }

    /* الورقة تصل مقسّمة الصفحات جاهزة من صفحة التطبيق (تقسيم Paged.js
       لا يعمل في نافذة خفية)، فيكفي هنا اكتمال التحميل وجهوزية الخطوط */
    private func poll() {
        guard phase == .loading else { return }
        if Date().timeIntervalSince(startedAt) > 120 {
            NSLog("AlMujtahedPrint: timeout — opening panel anyway")
            openPrintPanel()
            return
        }
        webView.evaluateJavaScript("document.readyState") { [weak self] result, _ in
            guard let self, self.phase == .loading else { return }
            guard (result as? String) == "complete" else { return }
            self.pollTimer?.invalidate()
            self.pollTimer = nil
            self.webView.evaluateJavaScript("document.fonts && document.fonts.ready ? document.fonts.ready.then(function () { return true; }) : true") { [weak self] _, _ in
                guard let self, self.phase == .loading else { return }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
                    self?.openPrintPanel()
                }
            }
        }
    }

    private func openPrintPanel() {
        guard phase == .loading else { return }
        NSLog("AlMujtahedPrint: opening print panel")
        phase = .panel
        pollTimer?.invalidate()
        pollTimer = nil
        let info = NSPrintInfo()
        info.paperSize = NSSize(width: 595.28, height: 841.89)
        info.leftMargin = 0
        info.rightMargin = 0
        info.topMargin = 0
        info.bottomMargin = 0
        info.horizontalPagination = .fit
        info.verticalPagination = .automatic
        info.isHorizontallyCentered = false
        info.isVerticallyCentered = false
        let operation = webView.printOperation(with: info)
        operation.showsPrintPanel = true
        operation.showsProgressPanel = true
        currentOperation = operation
        NSApp.activate(ignoringOtherApps: true)
        if let window = presentingWindow {
            operation.runModal(
                for: window,
                delegate: self,
                didRun: #selector(NativePrinter.printOperationDidRun(_:success:contextInfo:)),
                contextInfo: nil
            )
        } else {
            operation.run()
            finishJob()
        }
    }

    @objc func printOperationDidRun(_ operation: NSPrintOperation, success: Bool, contextInfo: UnsafeMutableRawPointer?) {
        NSLog("AlMujtahedPrint: panel closed success=%@", success ? "true" : "false")
        finishJob()
    }

    private func finishJob() {
        currentOperation = nil
        pollTimer?.invalidate()
        pollTimer = nil
        webView.stopLoading()
        webView.loadHTMLString("", baseURL: nil)
        phase = .idle
        pump()
    }
}

final class AppWindow: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, NSWindowDelegate {
    let window: NSWindow
    private let webView: WKWebView
    var onQuit: (() -> Void)?
    private var quitting = false
    private var readingWindows: [ReadingWindow] = []

    init(url: URL) {
        let configuration = WKWebViewConfiguration()
        let contentController = WKUserContentController()
        configuration.userContentController = contentController
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = true
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        webView = WKWebView(frame: .zero, configuration: configuration)
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "المجتهد"
        window.minSize = NSSize(width: 900, height: 640)
        window.contentView = webView
        window.setFrameAutosaveName("AlMujtahedApp")
        if !window.setFrameUsingName("AlMujtahedApp") {
            window.setFrame(NSScreen.main?.visibleFrame ?? window.frame, display: true)
        }
        window.isReleasedWhenClosed = false
        super.init()
        contentController.add(self, name: "almujtahed")
        window.delegate = self
        webView.navigationDelegate = self
        webView.uiDelegate = self
        // مسح كاش الصفحات والسكريبتات فقط. بيانات الموقع والمحادثات والإعدادات تبقى.
        let store = WKWebsiteDataStore.default()
        store.removeData(
            ofTypes: [WKWebsiteDataTypeDiskCache, WKWebsiteDataTypeMemoryCache],
            modifiedSince: Date(timeIntervalSince1970: 0)
        ) { [weak self] in
            guard let self else { return }
            var request = URLRequest(url: url)
            request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
            self.webView.load(request)
        }
    }

    func show() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if navigationWantsDownload(navigationAction) {
            decisionHandler(.download)
            return
        }
        if navigationAction.navigationType == .linkActivated,
           let url = navigationAction.request.url,
           let host = url.host,
           host != "localhost", host != "127.0.0.1" {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        AppDownloads.shared.adopt(download, owner: self)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(responseWantsDownload(navigationResponse) ? .download : .allow)
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        AppDownloads.shared.adopt(download, owner: self)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        makeReadingWindow(configuration: configuration, navigationAction: navigationAction)
    }

    private func makeReadingWindow(configuration: WKWebViewConfiguration, navigationAction: WKNavigationAction) -> WKWebView? {
        if navigationWantsDownload(navigationAction) {
            return HiddenDownloadView(configuration: configuration).webView
        }
        if let url = navigationAction.request.url,
           let host = url.host,
           host != "localhost", host != "127.0.0.1" {
            NSWorkspace.shared.open(url)
            return nil
        }
        let reader = ReadingWindow(configuration: configuration)
        reader.openPopup = { [weak self] configuration, action in
            self?.makeReadingWindow(configuration: configuration, navigationAction: action)
        }
        reader.onClose = { [weak self, weak reader] in
            guard let self, let reader else { return }
            self.readingWindows.removeAll { $0 === reader }
        }
        readingWindows.append(reader)
        reader.show()
        return reader.webView
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert()
        alert.messageText = "المجتهد"
        alert.informativeText = message
        alert.addButton(withTitle: "موافق")
        alert.runModal()
        completionHandler()
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = "المجتهد"
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.addButton(withTitle: "موافق")
        alert.addButton(withTitle: "إلغاء")
        completionHandler(alert.runModal() == .alertFirstButtonReturn)
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        presentWebOpenPanel(on: window, parameters: parameters, completionHandler: completionHandler)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "almujtahed" else { return }
        if let text = message.body as? String {
            guard text == "quit", !quitting else { return }
            quitting = true
            onQuit?()
            return
        }
        guard let body = message.body as? [String: Any], let action = body["action"] as? String else { return }
        if action == "printHtml" {
            guard let html = body["html"] as? String, !html.isEmpty else { return }
            let base = (body["base"] as? String).flatMap { URL(string: $0) }
                ?? URL(string: "http://127.0.0.1:8085/")!
            NativePrinter.shared.enqueue(html: html, baseURL: base, presentingWindow: window)
            return
        }
        guard action == "chooseFolder" else { return }
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "اختيار"
        panel.message = body["prompt"] as? String ?? "اختر المجلد"
        NSApp.activate(ignoringOtherApps: true)
        panel.beginSheetModal(for: window) { [weak self] response in
            let path = response == .OK ? (panel.url?.path ?? "") : ""
            let wrapped = (try? JSONSerialization.data(withJSONObject: [path])).flatMap { String(data: $0, encoding: .utf8) } ?? "[\"\"]"
            let encoded = wrapped.dropFirst().dropLast()
            self?.webView.evaluateJavaScript("window.__almujtahedPick && window.__almujtahedPick(\(encoded))")
        }
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        guard !quitting else { return true }
        quitting = true
        onQuit?()
        return false
    }
}

final class WarmProgressBar: NSView {
    var fraction: CGFloat = 0 {
        didSet { needsDisplay = true }
    }

    override func draw(_ dirtyRect: NSRect) {
        let radius = bounds.height / 2
        let track = NSBezierPath(roundedRect: bounds, xRadius: radius, yRadius: radius)
        NSColor(srgbRed: 0.906, green: 0.863, blue: 0.796, alpha: 1).setFill()
        track.fill()

        let clamped = max(0, min(1, fraction))
        let width = max(clamped > 0 ? bounds.height : 0, bounds.width * clamped)
        let fillRect = NSRect(x: bounds.maxX - width, y: 0, width: width, height: bounds.height)
        let fill = NSBezierPath(roundedRect: fillRect, xRadius: radius, yRadius: radius)
        let amber = NSColor(srgbRed: 0.961, green: 0.620, blue: 0.043, alpha: 1)
        let emerald = NSColor(srgbRed: 0.063, green: 0.725, blue: 0.506, alpha: 1)
        if let gradient = NSGradient(colors: [emerald, amber]) {
            gradient.draw(in: fill, angle: 180)
        } else {
            emerald.setFill()
            fill.fill()
        }
    }
}

final class LiveDot: NSView {
    override func draw(_ dirtyRect: NSRect) {
        NSColor(srgbRed: 0.063, green: 0.725, blue: 0.506, alpha: 1).setFill()
        NSBezierPath(ovalIn: bounds.insetBy(dx: 0.5, dy: 0.5)).fill()
    }
}

final class Launcher: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private var window: NSWindow!
    private var appWindow: AppWindow?
    private var statusLabel: NSTextField!
    private var phaseLabel: NSTextField!
    private var elapsedLabel: NSTextField!
    private var progressBar: WarmProgressBar!
    private var speedValue: NSTextField!
    private var speedCaption: NSTextField!
    private var loadedCaption: NSTextField!
    private var remainCaption: NSTextField!
    private var elapsedCaption: NSTextField!
    private var percentValue: NSTextField!
    private var loadedValue: NSTextField!
    private var remainValue: NSTextField!
    private var openButton: NSButton!
    private var reinstallButton: NSButton!
    private var task: Process?
    private var displayTimer: Timer?
    private var probeTimer: Timer?
    private var openedBrowser = false
    private var ready = false
    private var checkingInterface = false
    private let startedAt = Date()
    private var readyAt: Date?
    private var lastSampleAt = Date()
    private var lastSampleBytes: Int64 = 0
    private var speedBps: Double = 0
    private var etaSeconds: TimeInterval = -1
    private var etaMarkedAt = Date()
    private let support = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/Al-Mujtahed", isDirectory: true)
    private var statusURL: URL { support.appendingPathComponent("status.txt") }
    private let interfaceURL = URL(string: "http://127.0.0.1:8085/?v=1.10.390")!
    private let ink = NSColor(srgbRed: 0.165, green: 0.133, blue: 0.102, alpha: 1)
    private let clay = NSColor(srgbRed: 0.710, green: 0.416, blue: 0.298, alpha: 1)
    private let emerald = NSColor(srgbRed: 0.184, green: 0.435, blue: 0.369, alpha: 1)
    private let muted = NSColor(srgbRed: 0.416, green: 0.361, blue: 0.302, alpha: 1)
    private let paper = NSColor(srgbRed: 0.984, green: 0.969, blue: 0.941, alpha: 1)

    /// التطبيق يسكن «التطبيقات» كأي تطبيق: إن شُغّل من التنزيلات أو غيرها
    /// نسخ نفسه إلى /Applications (أو ~/Applications) وفتح النسخة المنقولة
    /// ثم خرج، فتكون أيقونته هناك هي ما يشغّله دائمًا. نسخة أحدث أو مساوية
    /// مستقرة هناك تُفتح كما هي ولا تُستبدل.
    private var relocating = false

    private func relocateToApplicationsIfNeeded() -> Bool {
        if ProcessInfo.processInfo.environment["ALMUJTAHED_NO_RELOCATE"] == "1" { return false }
        let fm = FileManager.default
        let bundle = Bundle.main.bundleURL
        let homeApps = fm.homeDirectoryForCurrentUser.appendingPathComponent("Applications").path
        let appsDirs = ["/Applications", homeApps]
        if appsDirs.contains(where: { bundle.path.hasPrefix($0 + "/") }) { return false }
        let myVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0"
        // LaunchServices قد يرسل «إعادة فتح» لنسختنا الجارية بدل تشغيل المنقولة
        // (نفس معرّف الحزمة)، لذا نطلق المنقولة قسريًا كعملية جديدة ثم نخرج.
        func launchRelocated(_ dest: URL) -> Bool {
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/open")
            proc.arguments = ["-n", dest.path]
            do { try proc.run() } catch { return false }
            relocating = true
            DispatchQueue.main.async { NSApp.terminate(nil) }
            return true
        }
        for appsDir in appsDirs {
            let dest = URL(fileURLWithPath: appsDir).appendingPathComponent("المجتهد.app")
            if let existing = Bundle(url: dest),
               let ev = existing.infoDictionary?["CFBundleShortVersionString"] as? String,
               ev.compare(myVersion, options: .numeric) != .orderedAscending {
                if launchRelocated(dest) { return true }
                continue
            }
            do {
                try fm.createDirectory(atPath: appsDir, withIntermediateDirectories: true)
                if fm.fileExists(atPath: dest.path) { try fm.removeItem(at: dest) }
                try fm.copyItem(at: bundle, to: dest)
                if launchRelocated(dest) { return true }
            } catch {
                continue
            }
        }
        return false
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if relocateToApplicationsIfNeeded() { return }
        if !acquireLock() {
            let others = NSRunningApplication.runningApplications(withBundleIdentifier: "com.almujtahed.desktop")
            others.first { $0.processIdentifier != ProcessInfo.processInfo.processIdentifier }?
                .activate(options: [.activateAllWindows])
            NSApp.terminate(nil)
            return
        }
        registerAlmarai()
        buildWindow()
        beginSetup()
        refreshProgress(resetSpeed: true)
        let display = Timer(timeInterval: 10, repeats: true) { [weak self] _ in
            self?.refreshProgress(resetSpeed: false)
        }
        display.tolerance = 0.2
        RunLoop.main.add(display, forMode: .common)
        displayTimer = display
        let probe = Timer(timeInterval: 2, repeats: true) { [weak self] _ in
            self?.probeInterface()
        }
        RunLoop.main.add(probe, forMode: .common)
        probeTimer = probe
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        !ready
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag, !relocating, window != nil {
            if ready {
                showAppWindow()
            } else {
                window.makeKeyAndOrderFront(nil)
            }
            NSApp.activate(ignoringOtherApps: true)
        }
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        if relocating { return }
        displayTimer?.invalidate()
        probeTimer?.invalidate()
        shutdownServices()
        releaseLock()
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        true
    }

    private func registerAlmarai() {
        let folders = [
            Bundle.main.resourceURL?.appendingPathComponent("fonts"),
            Bundle.main.resourceURL?.appendingPathComponent("source/web_ui/static/fonts")
        ]
        for folder in folders.compactMap({ $0 }) {
            for name in ["Almarai-Regular.ttf", "Almarai-Bold.ttf"] {
                let url = folder.appendingPathComponent(name)
                guard FileManager.default.fileExists(atPath: url.path) else { continue }
                CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
            }
        }
    }

    private func almarai(_ size: CGFloat, bold: Bool) -> NSFont {
        let names = bold
            ? ["Almarai Bold", "Almarai-Bold"]
            : ["Almarai", "Almarai-Regular"]
        for name in names {
            if let font = NSFont(name: name, size: size) { return font }
        }
        return NSFont.systemFont(ofSize: size, weight: bold ? .bold : .regular)
    }

    private var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.10.390"
    }

    private func buildWindow() {
        let width: CGFloat = 760
        let height: CGFloat = 508
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: width, height: height),
            styleMask: [.titled, .closable, .miniaturizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "المجتهد"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.backgroundColor = NSColor(srgbRed: 0.945, green: 0.914, blue: 0.863, alpha: 1)
        window.isReleasedWhenClosed = false
        window.delegate = self
        let content = NSView(frame: NSRect(x: 0, y: 0, width: width, height: height))
        content.userInterfaceLayoutDirection = .rightToLeft
        window.contentView = content

        let headerIcon = bookIcon()
        headerIcon.frame = NSRect(x: width - 32 - 34, y: height - 30 - 34, width: 34, height: 34)
        content.addSubview(headerIcon)

        let title = text("المجتهد", size: 28, weight: .bold, color: ink)
        title.sizeToFit()
        let titleWidth = title.frame.width + 4
        title.frame = NSRect(x: headerIcon.frame.minX - 8 - titleWidth, y: headerIcon.frame.midY - 20, width: titleWidth, height: 40)
        content.addSubview(title)

        let version = text(appVersion, size: 16, weight: .bold, color: NSColor(srgbRed: 0.063, green: 0.725, blue: 0.506, alpha: 1))
        version.alignment = .left
        version.baseWritingDirection = .leftToRight
        version.frame = NSRect(x: 32, y: height - 30 - 22, width: 88, height: 24)
        content.addSubview(version)

        let edition = text("نسخة تجريبية", size: 12, weight: .regular, color: muted)
        edition.alignment = .left
        edition.baseWritingDirection = .leftToRight
        edition.frame = NSRect(x: 32, y: version.frame.minY - 18, width: 120, height: 18)
        content.addSubview(edition)

        statusLabel = text("جاري تهيئة التطبيق", size: 14, weight: .regular, color: muted)
        statusLabel.frame = NSRect(x: 32, y: height - 118, width: width - 64, height: 24)
        content.addSubview(statusLabel)

        let card = NSBox(frame: NSRect(x: 28, y: 118, width: width - 56, height: 252))
        card.boxType = .custom
        card.cornerRadius = 16
        card.borderWidth = 1
        card.borderColor = NSColor(srgbRed: 0.906, green: 0.863, blue: 0.796, alpha: 1)
        card.fillColor = paper
        card.titlePosition = .noTitle
        card.shadow = {
            let shadow = NSShadow()
            shadow.shadowColor = NSColor.black.withAlphaComponent(0.05)
            shadow.shadowOffset = NSSize(width: 0, height: -1)
            shadow.shadowBlurRadius = 8
            return shadow
        }()
        content.addSubview(card)

        let cardIcon = iconBox(symbol: "arrow.down.circle", tint: NSColor(srgbRed: 0.961, green: 0.620, blue: 0.043, alpha: 1), fill: NSColor(srgbRed: 0.961, green: 0.620, blue: 0.043, alpha: 0.14))
        cardIcon.frame = NSRect(x: card.bounds.width - 24 - 36, y: card.bounds.height - 24 - 36, width: 36, height: 36)
        card.addSubview(cardIcon)

        let cardTitle = text("تشغيل المجتهد", size: 18, weight: .bold, color: ink)
        cardTitle.frame = NSRect(x: 110, y: card.bounds.height - 24 - 32, width: card.bounds.width - 110 - 72, height: 32)
        card.addSubview(cardTitle)

        percentValue = text("0%", size: 13, weight: .bold, color: muted)
        percentValue.alignment = .center
        percentValue.frame = NSRect(x: 24, y: card.bounds.height - 22 - 30, width: 72, height: 30)
        percentValue.wantsLayer = true
        percentValue.layer?.backgroundColor = NSColor(srgbRed: 0.906, green: 0.863, blue: 0.796, alpha: 0.7).cgColor
        percentValue.layer?.cornerRadius = 8
        card.addSubview(percentValue)

        phaseLabel = text("جاري تهيئة التطبيق", size: 20, weight: .bold, color: ink)
        phaseLabel.maximumNumberOfLines = 2
        phaseLabel.frame = NSRect(x: 24, y: card.bounds.height - 128, width: card.bounds.width - 48, height: 56)
        card.addSubview(phaseLabel)

        progressBar = WarmProgressBar(frame: NSRect(x: 24, y: 108, width: card.bounds.width - 48, height: 8))
        card.addSubview(progressBar)

        let column = (card.bounds.width - 48 - 36) / 4
        speedValue = footerStat("سرعة التحميل", x: 24 + (column + 12) * 3, width: column, in: card, caption: &speedCaption)
        loadedValue = footerStat("الحجم المحمل", x: 24 + (column + 12) * 2, width: column, in: card, caption: &loadedCaption)
        remainValue = footerStat("الحجم المتبقي", x: 24 + (column + 12), width: column, in: card, caption: &remainCaption)
        elapsedLabel = footerStat("الوقت المتبقي", x: 24, width: column, in: card, caption: &elapsedCaption)

        let gap: CGFloat = 12
        let buttonWidth = (width - 56 - gap * 3) / 4
        let buttonY: CGFloat = 36
        openButton = actionButton("فتح التطبيق", action: #selector(openInterface), x: width - 28 - buttonWidth, width: buttonWidth, tint: NSColor(srgbRed: 0.063, green: 0.725, blue: 0.506, alpha: 1))
        openButton.frame.origin.y = buttonY
        setOpenButtonEnabled(false)
        content.addSubview(openButton)
        let quitButton = actionButton("إغلاق التطبيق", action: #selector(quitApplication), x: width - 28 - buttonWidth * 2 - gap, width: buttonWidth, tint: muted)
        quitButton.frame.origin.y = buttonY
        content.addSubview(quitButton)
        let deleteButton = actionButton("حذف التطبيق", action: #selector(deleteApplication), x: width - 28 - buttonWidth * 3 - gap * 2, width: buttonWidth, tint: NSColor(srgbRed: 0.55, green: 0.23, blue: 0.20, alpha: 1))
        deleteButton.frame.origin.y = buttonY
        content.addSubview(deleteButton)
        reinstallButton = actionButton("إعادة التنصيب", action: #selector(reinstallSetup), x: 28, width: buttonWidth, tint: clay)
        reinstallButton.frame.origin.y = buttonY
        setReinstallEnabled(false)
        content.addSubview(reinstallButton)

        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }


    private func bookIcon() -> NSImageView {
        let image = NSImage(systemSymbolName: "book.closed", accessibilityDescription: "كتاب") ?? NSImage()
        let view = NSImageView(image: image)
        view.symbolConfiguration = NSImage.SymbolConfiguration(pointSize: 28, weight: .semibold)
        view.contentTintColor = NSColor(srgbRed: 0.063, green: 0.725, blue: 0.506, alpha: 1)
        return view
    }

    private func iconBox(symbol: String, tint: NSColor, fill: NSColor) -> NSView {
        let box = NSView(frame: NSRect(x: 0, y: 0, width: 34, height: 34))
        box.wantsLayer = true
        box.layer?.backgroundColor = fill.cgColor
        box.layer?.cornerRadius = 8
        let image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil) ?? NSImage()
        let view = NSImageView(image: image)
        view.symbolConfiguration = NSImage.SymbolConfiguration(pointSize: 16, weight: .semibold)
        view.contentTintColor = tint
        view.frame = NSRect(x: 7, y: 7, width: 20, height: 20)
        box.addSubview(view)
        return box
    }

    private func footerStat(_ title: String, x: CGFloat, width: CGFloat, in parent: NSView, caption: inout NSTextField!) -> NSTextField {
        caption = text(title, size: 13, weight: .regular, color: muted)
        caption.frame = NSRect(x: x, y: 52, width: width, height: 22)
        parent.addSubview(caption)
        let value = text("—", size: 18, weight: .bold, color: ink)
        value.frame = NSRect(x: x, y: 22, width: width, height: 28)
        parent.addSubview(value)
        return value
    }

    private func actionButton(_ title: String, action: Selector, x: CGFloat, width: CGFloat, tint: NSColor) -> NSButton {
        let button = NSButton(title: title, target: self, action: action)
        button.isBordered = false
        button.wantsLayer = true
        button.layer?.backgroundColor = tint.withAlphaComponent(0.14).cgColor
        button.layer?.cornerRadius = 6
        button.layer?.masksToBounds = true
        button.frame = NSRect(x: x, y: 19, width: width, height: 40)
        button.font = almarai(16, bold: true)
        button.attributedTitle = NSAttributedString(
            string: title,
            attributes: [.font: almarai(16, bold: true), .foregroundColor: tint]
        )
        button.contentTintColor = tint
        return button
    }

    private func text(_ value: String, size: CGFloat, weight: NSFont.Weight, color: NSColor) -> NSTextField {
        let field = NSTextField(labelWithString: value)
        field.font = almarai(size, bold: weight.rawValue >= NSFont.Weight.semibold.rawValue)
        field.textColor = color
        field.alignment = .right
        field.baseWritingDirection = .rightToLeft
        field.lineBreakMode = .byWordWrapping
        return field
    }

    private func setOpenButtonEnabled(_ enabled: Bool) {
        openButton.isEnabled = enabled
        openButton.alphaValue = enabled ? 1 : 0.38
        openButton.keyEquivalent = enabled ? "\r" : ""
    }

    private func setReinstallEnabled(_ enabled: Bool) {
        reinstallButton.isEnabled = enabled
        reinstallButton.alphaValue = enabled ? 1 : 0.38
    }

    @objc private func reinstallSetup() {
        guard reinstallButton.isEnabled else { return }
        let alert = NSAlert()
        alert.messageText = "إعادة التنصيب"
        alert.informativeText = "ستُعاد تهيئة التطبيق من جديد. المحادثات تبقى."
        alert.addButton(withTitle: "إعادة التنصيب")
        alert.addButton(withTitle: "إلغاء")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        phaseLabel.stringValue = "جاري تهيئة التطبيق"
        setReinstallEnabled(false)
        setOpenButtonEnabled(false)
        ready = false
        speedBps = 0
        etaSeconds = -1
        lastSampleBytes = 0
        shutdownServices()
        let runtime = support.appendingPathComponent("runtime")
        let fm = FileManager.default
        for relative in [
            "models/gguf",
            "qdrant_service/snapshots",
            "qdrant_service/storage/tmp",
            "qdrant_service/storage/collections",
            "shamela4_data/_git_tmp",
            "web_ui/bootstrap_status.json",
            "web_ui/local_source.json"
        ] {
            try? fm.removeItem(at: runtime.appendingPathComponent(relative))
        }
        beginSetup()
    }

    private func filesLookDamaged() -> Bool {
        if readBootstrap()?.needsReinstall == true || readBootstrap()?.phase == "error" {
            return true
        }
        let model = support.appendingPathComponent("runtime/models/gguf/almojtahed-embedding-8b-Q4_K_M.gguf")
        if let size = byteCount(model), size > 0, size < 1_000_000_000, !incompleteModelExists() {
            return true
        }
        return false
    }

    private func beginSetup() {
        let choice = support.appendingPathComponent("runtime/web_ui/local_source.json")
        if FileManager.default.fileExists(atPath: choice.path) || dataAlreadyInstalled() {
            startEngine()
            return
        }
        if cloudAlreadyStarted() {
            writeSource(mode: "cloud", path: nil)
            startEngine()
            return
        }
        askSource()
    }

    private func databaseAlreadyPresent() -> Bool {
        let collection = support.appendingPathComponent("runtime/qdrant_service/storage/collections/shamela_almojtahed_8b_dense")
        if folderHasChild(collection) { return true }
        let snapshot = support.appendingPathComponent("runtime/qdrant_service/snapshots/shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot")
        return (byteCount(snapshot) ?? 0) > 1_000_000_000
    }

    private func dataAlreadyInstalled() -> Bool {
        let model = support.appendingPathComponent("runtime/models/gguf/almojtahed-embedding-8b-Q4_K_M.gguf")
        guard let size = byteCount(model), size > 1_000_000_000 else { return false }
        let shamela = support.appendingPathComponent("runtime/shamela4_data")
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: shamela.path, isDirectory: &isDir), isDir.boolValue else { return false }
        let collection = support.appendingPathComponent("runtime/qdrant_service/storage/collections/shamela_almojtahed_8b_dense")
        if FileManager.default.fileExists(atPath: collection.path) { return true }
        let snapshot = support.appendingPathComponent("runtime/qdrant_service/snapshots/shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot")
        return (byteCount(snapshot) ?? 0) > 1_000_000_000
    }

    private func cloudAlreadyStarted() -> Bool {
        incompleteModelExists() || snapshotDownloadBytes() != nil
    }

    private func writeSource(mode: String, path: String?) {
        let directory = support.appendingPathComponent("runtime/web_ui", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        var payload: [String: String] = ["mode": mode]
        if let path { payload["path"] = path }
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return }
        try? data.write(to: directory.appendingPathComponent("local_source.json"))
    }

    private func askSource() {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "مصدر البيانات"
        alert.informativeText = "نموذج التضمين، والمكتبة الشاملة، وقاعدة البيانات (السنابشوت). السحابة تكمل التنصيب بالتنزيل الحالي، والمحلية تنسخها من مجلد على القرص."
        alert.addButton(withTitle: "سحابة")
        alert.addButton(withTitle: "محلية")
        if alert.runModal() == .alertSecondButtonReturn {
            guard let folder = pickLocalFolder() else { return }
            writeSource(mode: "local", path: folder)
        } else {
            writeSource(mode: "cloud", path: nil)
        }
        startEngine()
    }

    private func pickLocalFolder() -> String? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = false
        panel.allowsMultipleSelection = false
        panel.prompt = "اختيار"
        panel.message = "اختر المجلد الذي يحتوي على نموذج التضمين والمكتبة الشاملة وقاعدة البيانات"
        NSApp.activate(ignoringOtherApps: true)
        guard panel.runModal() == .OK, let url = panel.url else {
            askSource()
            return nil
        }
        if localFolderIsValid(url) { return url.path }
        let warn = NSAlert()
        warn.messageText = "المجلد غير مكتمل"
        warn.informativeText = "يلزم أن يحتوي المجلد على نموذج التضمين والمكتبة الشاملة وقاعدة البيانات."
        warn.addButton(withTitle: "اختيار مجلد آخر")
        warn.addButton(withTitle: "سحابة")
        if warn.runModal() == .alertSecondButtonReturn {
            writeSource(mode: "cloud", path: nil)
            startEngine()
            return nil
        }
        return pickLocalFolder()
    }

    private func localFolderIsValid(_ url: URL) -> Bool {
        let candidates = [url, url.appendingPathComponent("المجتهد-محلي")]
        return candidates.contains { modelInFolder($0) && shamelaInFolder($0) && databaseInFolder($0) }
    }

    private func modelInFolder(_ root: URL) -> Bool {
        let names = ["model/almojtahed-embedding-8b-Q4_K_M.gguf", "models/gguf/almojtahed-embedding-8b-Q4_K_M.gguf"]
        return names.contains { (byteCount(root.appendingPathComponent($0)) ?? 0) > 1_000_000_000 }
    }

    private func shamelaInFolder(_ root: URL) -> Bool {
        let names = ["shamela", "shamela4_data"]
        return names.contains { folderHasChild(root.appendingPathComponent($0)) }
    }

    private func databaseInFolder(_ root: URL) -> Bool {
        let snapshotNames = [
            "database/snapshot/shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot",
            "qdrant_service/snapshots/shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot"
        ]
        if snapshotNames.contains(where: { (byteCount(root.appendingPathComponent($0)) ?? 0) > 1_000_000_000 }) {
            return true
        }
        let storageNames = [
            "database/storage/collections/shamela_almojtahed_8b_dense",
            "qdrant_service/storage/collections/shamela_almojtahed_8b_dense"
        ]
        return storageNames.contains { folderHasChild(root.appendingPathComponent($0)) }
    }

    private func folderHasChild(_ url: URL) -> Bool {
        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue else { return false }
        return ((try? FileManager.default.contentsOfDirectory(atPath: url.path))?.isEmpty == false)
    }

    private func startEngine() {
        let script = Bundle.main.resourceURL!.appendingPathComponent("launch.sh")
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = [script.path]
        task.terminationHandler = { [weak self] process in
            DispatchQueue.main.async {
                guard let self, !self.ready else { return }
                if process.terminationStatus != 0 {
                    self.phaseLabel.stringValue = "تعذر تشغيل التطبيق"
                    self.statusLabel.stringValue = "تعذر تشغيل التطبيق"
                    self.setReinstallEnabled(true)
                }
            }
        }
        do {
            try task.run()
            self.task = task
        } catch {
            phaseLabel.stringValue = "تعذر تشغيل المجتهد"
        }
    }

    @objc private func openInterface() {
        guard ready else { return }
        showAppWindow()
    }

    private func showAppWindow() {
        if appWindow == nil {
            appWindow = AppWindow(url: interfaceURL)
            appWindow?.onQuit = { [weak self] in
                self?.quitApplication()
            }
        }
        appWindow?.show()
    }

    @objc private func quitApplication() {
        phaseLabel.stringValue = "سيتم إغلاق التطبيق"
        shutdownServices()
        NSApp.terminate(nil)
    }

    @objc private func deleteApplication() {
        let alert = NSAlert()
        alert.messageText = "حذف التطبيق"
        alert.informativeText = "سيتم إغلاق التطبيق وحذف بياناته."
        alert.alertStyle = .critical
        alert.addButton(withTitle: "حذف")
        alert.addButton(withTitle: "إلغاء")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        phaseLabel.stringValue = "سيتم إغلاق التطبيق"
        shutdownServices()
        let fm = FileManager.default
        try? fm.removeItem(at: support)
        let logs = fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Al-Mujtahed")
        try? fm.removeItem(at: logs)
        let bundle = "'" + Bundle.main.bundlePath.replacingOccurrences(of: "'", with: "'\\''") + "'"
        let remove = Process()
        remove.executableURL = URL(fileURLWithPath: "/bin/sh")
        remove.arguments = ["-c", "nohup sh -c 'sleep 1; rm -rf \(bundle)' >/dev/null 2>&1 &"]
        try? remove.run()
        NSApp.terminate(nil)
    }

    private func shutdownServices() {
        stopOwnedProcess(named: "qdrant.pid", marker: "qdrant")
        stopOwnedProcess(named: "init.pid", marker: "init_coolify_data.py")
        if let task, task.isRunning {
            task.terminate()
        }
        stopListener(port: 6333, marker: "Al-Mujtahed")
        stopListener(port: 8085, marker: "server.py")
    }

    private func refreshProgress(resetSpeed: Bool) {
        if ready { return }
        var message = currentStatus()
        if let boot = readBootstrap(), boot.phase == "snapshot", !boot.message.isEmpty {
            message = boot.message
        }
        if !message.isEmpty {
            let phrase = publicPhase(message)
            phaseLabel.stringValue = phrase
            statusLabel.stringValue = phrase
        }
        let transfer = transferState()
        let now = Date()
        let grew = !resetSpeed && transfer.received > lastSampleBytes
        let delta = now.timeIntervalSince(lastSampleAt)
        if grew, delta >= 1 {
            let measured = Double(transfer.received - lastSampleBytes) / delta
            if measured >= 1 { speedBps = measured }
        }
        lastSampleBytes = transfer.received
        lastSampleAt = now

        let percent = ready ? 100.0 : displayedPercent(message: message, transfer: transfer)
        let installing = readBootstrap()?.phase == "install"
        let shown = installing && transfer.expected > 0
            ? min(100, Double(max(transfer.received, 0)) / Double(transfer.expected) * 100)
            : percent
        progressBar.fraction = CGFloat(shown / 100)
        percentValue.stringValue = "\(Int(shown.rounded()))%"
        if installing {
            speedCaption?.stringValue = "نسبة التركيب"
            loadedCaption?.stringValue = ""
            remainCaption?.stringValue = ""
            elapsedCaption?.stringValue = ""
            speedValue.stringValue = percentValue.stringValue
            loadedValue.stringValue = ""
            remainValue.stringValue = ""
            elapsedLabel.stringValue = ""
        } else {
            speedCaption?.stringValue = "سرعة التحميل"
            loadedCaption?.stringValue = "الحجم المحمل"
            remainCaption?.stringValue = "الحجم المتبقي"
            elapsedCaption?.stringValue = "الوقت المتبقي"
            speedValue.stringValue = speedText()
            loadedValue.stringValue = transfer.received > 0 ? bytesText(transfer.received) : "—"
            let remain = max(0, transfer.expected - transfer.received)
            remainValue.stringValue = transfer.expected > 0 ? bytesText(remain) : "—"
            elapsedLabel.stringValue = remainingClock(remain, reset: grew)
        }
        let damaged = filesLookDamaged()
        setReinstallEnabled(damaged)
        if damaged {
            phaseLabel.stringValue = "تعذر تشغيل التطبيق"
        }
    }

    private func publicPhase(_ message: String) -> String {
        if message.contains("تعذر") || message.contains("تلف") || message.contains("انقطاع") || message.contains("يلزم") {
            return "تعذر تشغيل التطبيق"
        }
        if message.contains("فتح التطبيق") || message.contains("الواجهة") {
            return "جاري فتح التطبيق"
        }
        switch readBootstrap()?.phase {
        case "download", "install", "snapshot", "local":
            return "جاري تثبيت الملفات"
        default:
            break
        }
        let installing = ["بايثون", "Python", "مكتبات", "بيئة", "تثبيت", "تنزيل", "سحب", "نموذج", "تضمين", "محرك", "سنابشوت", "قاعدة", "Qdrant"]
        if installing.contains(where: { message.contains($0) }) || incompleteModelExists() {
            let stillWorking = message.contains("جاري") || message.contains("سحب") || message.contains("تنزيل") || message.contains("تثبيت")
            if !stillWorking && (message.contains("موجود") || message.contains("تم تشغيل") || message.contains("يعمل")) {
                return "جاري فتح التطبيق"
            }
            return "جاري تثبيت الملفات"
        }
        if message.contains("تهيئة") || message.contains("تجهيز") || message.isEmpty {
            return "جاري تهيئة التطبيق"
        }
        return "جاري فتح التطبيق"
    }

    private func incompleteModelExists() -> Bool {
        let cache = support.appendingPathComponent("runtime/models/gguf/.cache/huggingface/download")
        guard let names = try? FileManager.default.contentsOfDirectory(atPath: cache.path) else { return false }
        return names.contains { $0.hasSuffix(".incomplete") }
    }

    private func displayedPercent(message: String, transfer: (received: Int64, expected: Int64)) -> Double {
        if readBootstrap()?.phase == "local" { return transfer.expected > 0 ? min(90, Double(max(transfer.received, 0)) / Double(transfer.expected) * 90) : 8 }
        if readBootstrap()?.phase == "download" || readBootstrap()?.phase == "install", transfer.expected > 0 {
            return min(90, Double(max(transfer.received, 0)) / Double(transfer.expected) * 90)
        }
        if transfer.expected > transfer.received && transfer.received > 0 {
            return min(90, Double(transfer.received) / Double(transfer.expected) * 90)
        }
        if message.contains("بيئة بايثون") { return 8 }
        if message.contains("مكتبات") { return 20 }
        if message.contains("تنزيل محرك") { return 34 }
        if message.contains("تم تشغيل Qdrant") || message.contains("Qdrant يعمل") { return 42 }
        if message.contains("موجود") || message.contains("سنابشوت") || message.contains("الشاملة") { return 88 }
        if message.contains("الواجهة") || message.contains("فتح التطبيق") { return 94 }
        if message.contains("تثبيت الملفات") || message.contains("تثبيت") { return 22 }
        if message.contains("تهيئة") || message.contains("تجهيز") { return 8 }
        if transfer.expected > 0 && transfer.received > 0 {
            return min(90, Double(transfer.received) / Double(transfer.expected) * 90)
        }
        return 4
    }

    private func markReady() {
        ready = true
        readyAt = Date()
        progressBar.fraction = 1
        percentValue.stringValue = "100%"
        speedValue.stringValue = speedText()
        let transfer = transferState()
        if transfer.received > 0 {
            loadedValue.stringValue = bytesText(transfer.received)
        }
        remainValue.stringValue = "0 ميجا"
        elapsedLabel.stringValue = "00:00:00"
        statusLabel.stringValue = "جاري فتح التطبيق"
        phaseLabel.stringValue = "جاري فتح التطبيق"
        setOpenButtonEnabled(true)
        window.orderOut(nil)
        if !openedBrowser {
            openedBrowser = true
            showAppWindow()
        }
    }

    private func probeInterface() {
        if checkingInterface || ready { return }
        checkingInterface = true
        var request = URLRequest(url: interfaceURL)
        request.timeoutInterval = 1.2
        URLSession.shared.dataTask(with: request) { _, response, _ in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async {
                self.checkingInterface = false
                guard ok else { return }
                if !self.openedBrowser {
                    self.openedBrowser = true
                    self.showAppWindow()
                }
                self.setOpenButtonEnabled(true)
                if self.databaseAlreadyPresent() {
                    self.markReady()
                    return
                }
                if let phase = self.readBootstrap()?.phase, phase == "download" || phase == "install" || phase == "snapshot" || phase == "local" || phase == "error" || self.filesLookDamaged() {
                    return
                }
                self.markReady()
            }
        }.resume()
    }

    private func transferState() -> (received: Int64, expected: Int64) {
        if readBootstrap()?.phase == "local", let boot = readBootstrap(), boot.expected > 0 {
            return (min(max(boot.received, 0), boot.expected), boot.expected)
        }
        let finalFile = support.appendingPathComponent("runtime/models/gguf/almojtahed-embedding-8b-Q4_K_M.gguf")
        if let size = byteCount(finalFile), size > 1_000_000_000 {
            let expectedSnapshot = readBootstrap()?.expected ?? 184_683_593_728
            let phase = readBootstrap()?.phase
            if phase == "download" {
                let partial = snapshotDownloadBytes() ?? readBootstrap()?.received ?? 0
                return (min(partial, expectedSnapshot), expectedSnapshot)
            }
            if phase == "install" {
                let received = readBootstrap()?.received ?? 0
                return (min(max(received, 0), expectedSnapshot), expectedSnapshot)
            }
            return (size, size)
        }
        var received: Int64 = 0
        var newest = Date.distantPast
        let cache = support.appendingPathComponent("runtime/models/gguf/.cache/huggingface/download")
        if let names = try? FileManager.default.contentsOfDirectory(atPath: cache.path) {
            for name in names where name.hasSuffix(".incomplete") {
                let url = cache.appendingPathComponent(name)
                var info = stat()
                guard stat(url.path, &info) == 0 else { continue }
                let modified = Date(timeIntervalSince1970: TimeInterval(info.st_mtimespec.tv_sec))
                if modified >= newest {
                    newest = modified
                    received = Int64(info.st_size)
                }
            }
        }
        let expected = max(Int64(4_724_464_026), received)
        return (received, expected)
    }

    private func snapshotDownloadBytes() -> Int64? {
        let root = support.appendingPathComponent("runtime/qdrant_service/snapshots")
        let finalName = "shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot"
        if let size = byteCount(root.appendingPathComponent(finalName + ".partial")), size > 0 {
            return size
        }
        if let size = byteCount(root.appendingPathComponent(finalName)), size > 0 {
            return size
        }
        let cache = root.appendingPathComponent(".cache/huggingface/download")
        guard let names = try? FileManager.default.contentsOfDirectory(atPath: cache.path) else { return nil }
        var received: Int64 = 0
        for name in names where name.hasSuffix(".incomplete") {
            received = max(received, byteCount(cache.appendingPathComponent(name)) ?? 0)
        }
        return received > 0 ? received : nil
    }

    private struct Bootstrap {
        var phase: String
        var message: String
        var expected: Int64
        var received: Int64
        var needsReinstall: Bool
    }

    private func readBootstrap() -> Bootstrap? {
        let url = support.appendingPathComponent("runtime/web_ui/bootstrap_status.json")
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        return Bootstrap(
            phase: obj["phase"] as? String ?? "",
            message: obj["message"] as? String ?? "",
            expected: (obj["expected_bytes"] as? NSNumber)?.int64Value ?? 0,
            received: (obj["received_bytes"] as? NSNumber)?.int64Value ?? 0,
            needsReinstall: obj["needs_reinstall"] as? Bool ?? false
        )
    }

    private func byteCount(_ url: URL) -> Int64? {
        var info = stat()
        guard stat(url.path, &info) == 0 else { return nil }
        return Int64(info.st_size)
    }

    private func speedText() -> String {
        if speedBps < 1 { return "—" }
        if speedBps >= 1_048_576 { return plain("%.2f", speedBps / 1_048_576) + " ميجا/ث" }
        return plain("%.0f", speedBps / 1024) + " كيلو/ث"
    }

    private func bytesText(_ bytes: Int64) -> String {
        if bytes <= 0 { return "0 ميجا" }
        let gb = Double(bytes) / 1_073_741_824
        if gb >= 1 { return plain("%.2f", gb) + " جيجا" }
        return plain("%.0f", Double(bytes) / 1_048_576) + " ميجا"
    }

    private func plain(_ format: String, _ value: Double) -> String {
        String(format: format, locale: Locale(identifier: "en_US_POSIX"), value)
    }

    private func remainingClock(_ remain: Int64, reset: Bool) -> String {
        if remain <= 0 { return "00:00:00" }
        guard speedBps >= 1 else { return "—" }
        let now = Date()
        if reset || etaSeconds < 0 {
            etaSeconds = Double(remain) / speedBps
            etaMarkedAt = now
        }
        return clock(max(0, etaSeconds - now.timeIntervalSince(etaMarkedAt)))
    }

    private func clock(_ interval: TimeInterval) -> String {
        let total = max(0, Int(interval))
        return String(format: "%02d:%02d:%02d", total / 3600, (total % 3600) / 60, total % 60)
    }

    private func currentStatus() -> String {
        (try? String(contentsOf: statusURL, encoding: .utf8))?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    private func stopListener(port: Int32, marker: String) {
        let task = Process()
        let pipe = Pipe()
        task.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        task.arguments = ["-nP", "-iTCP:\(port)", "-sTCP:LISTEN", "-t"]
        task.standardOutput = pipe
        try? task.run()
        task.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""
        for raw in output.split(whereSeparator: \.isWhitespace) {
            guard let pid = Int32(raw), pid > 0, command(for: pid).contains(marker) else { continue }
            kill(pid, SIGTERM)
        }
    }

    private func stopOwnedProcess(named file: String, marker: String) {
        let url = support.appendingPathComponent(file)
        guard let text = try? String(contentsOf: url, encoding: .utf8),
              let pid = Int32(text.trimmingCharacters(in: .whitespacesAndNewlines)),
              pid > 0,
              command(for: pid).contains(marker) else { return }
        kill(pid, SIGTERM)
    }

    private func command(for pid: Int32) -> String {
        let task = Process()
        let pipe = Pipe()
        task.executableURL = URL(fileURLWithPath: "/bin/ps")
        task.arguments = ["-p", String(pid), "-o", "command="]
        task.standardOutput = pipe
        try? task.run()
        task.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8) ?? ""
    }

    private func acquireLock() -> Bool {
        try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        let fd = open(support.appendingPathComponent("app.lock").path, O_CREAT | O_RDWR, 0o644)
        if fd < 0 { return true }
        if flock(fd, LOCK_EX | LOCK_NB) != 0 { return false }
        return true
    }

    private func releaseLock() {
        let fd = open(support.appendingPathComponent("app.lock").path, O_RDWR)
        if fd >= 0 {
            flock(fd, LOCK_UN)
            close(fd)
        }
    }
}

let app = NSApplication.shared
let delegate = Launcher()
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()
