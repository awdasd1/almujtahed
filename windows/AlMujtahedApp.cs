using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.Globalization;
using System.Net;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace AlMujtahed;

static class Program
{
    const int HWND_BROADCAST = 0xffff;

    [STAThread]
    static void Main()
    {
        try
        {
            Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using var mutex = new Mutex(true, @"Local\com.almujtahed.desktop", out var created);
            if (!created)
            {
                PostMessage((IntPtr)HWND_BROADCAST, Native.ActivateMessage, IntPtr.Zero, IntPtr.Zero);
                return;
            }
            Directory.CreateDirectory(Paths.Support);
            Application.Run(new InstallerForm());
            GC.KeepAlive(mutex);
        }
        catch (Exception ex)
        {
            try
            {
                File.WriteAllText(Path.Combine(AppContext.BaseDirectory, "startup-error.txt"), ex.ToString());
            }
            catch { }
            MessageBox.Show(ex.Message, "المجتهد", MessageBoxButtons.OK, MessageBoxIcon.Error,
                MessageBoxDefaultButton.Button1, MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign);
        }
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern bool PostMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);
}

static class Native
{
    public static readonly int ActivateMessage = RegisterWindowMessage("ALMUJTAHED_OPEN");

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int RegisterWindowMessage(string lpString);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("iphlpapi.dll", SetLastError = true)]
    static extern uint GetExtendedTcpTable(IntPtr table, ref int size, bool order, int family, int tableClass, uint reserved);

    [StructLayout(LayoutKind.Sequential)]
    struct TcpRow
    {
        public uint State;
        public uint LocalAddr;
        public uint LocalPort;
        public uint RemoteAddr;
        public uint RemotePort;
        public uint OwningPid;
    }

    public static List<int> ListeningPids(int port)
    {
        var found = new List<int>();
        int size = 0;
        GetExtendedTcpTable(IntPtr.Zero, ref size, true, 2, 3, 0);
        if (size <= 0) return found;
        var buffer = Marshal.AllocHGlobal(size);
        try
        {
            if (GetExtendedTcpTable(buffer, ref size, true, 2, 3, 0) != 0) return found;
            int count = Marshal.ReadInt32(buffer);
            var row = IntPtr.Add(buffer, 4);
            int rowSize = Marshal.SizeOf<TcpRow>();
            for (var i = 0; i < count; i++)
            {
                var entry = Marshal.PtrToStructure<TcpRow>(row);
                int localPort = (int)(((entry.LocalPort & 0xFF) << 8) | ((entry.LocalPort & 0xFF00) >> 8));
                if (localPort == port) found.Add((int)entry.OwningPid);
                row = IntPtr.Add(row, rowSize);
            }
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
        return found;
    }
}

static class Paths
{
    public static string Support => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Al-Mujtahed");
    public static string Runtime => Path.Combine(Support, "runtime");
    public static string StatusFile => Path.Combine(Support, "status.txt");
    public static string BootstrapFile => Path.Combine(Runtime, "web_ui", "bootstrap_status.json");
    public static string ModelFile => Path.Combine(Runtime, "models", "gguf", "almojtahed-embedding-8b-Q4_K_M.gguf");
    public static string Snapshots => Path.Combine(Runtime, "qdrant_service", "snapshots");
    public const string SnapshotName = "shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot";
    public const long SnapshotExpected = 184_683_593_728L;
    public const long ModelExpected = 4_724_464_026L;
}

static class AppFonts
{
    static readonly PrivateFontCollection Collection = new();
    static readonly FontFamily Family;

    static AppFonts()
    {
        foreach (var folder in new[]
        {
            Path.Combine(AppContext.BaseDirectory, "fonts"),
            Path.Combine(AppContext.BaseDirectory, "source", "web_ui", "static", "fonts")
        })
        {
            foreach (var name in new[] { "Almarai-Regular.ttf", "Almarai-Bold.ttf" })
            {
                var path = Path.Combine(folder, name);
                if (File.Exists(path)) Collection.AddFontFile(path);
            }
        }
        Family = Collection.Families.FirstOrDefault(family => family.Name.Contains("Almarai", StringComparison.OrdinalIgnoreCase))
            ?? FontFamily.GenericSansSerif;
    }

    public static Font Make(float size, bool bold, float scale = 1f)
    {
        var style = bold && Family.IsStyleAvailable(FontStyle.Bold) ? FontStyle.Bold : FontStyle.Regular;
        if (scale < 1f) scale = 1f;
        return new Font(Family, size * scale * 96f / 72f, style, GraphicsUnit.Pixel);
    }
}

static class Palette
{
    public static readonly Color Canvas = Color.FromArgb(241, 233, 220);
    public static readonly Color Paper = Color.FromArgb(251, 247, 240);
    public static readonly Color Line = Color.FromArgb(231, 220, 203);
    public static readonly Color Ink = Color.FromArgb(42, 34, 26);
    public static readonly Color Clay = Color.FromArgb(181, 106, 76);
    public static readonly Color Emerald = Color.FromArgb(47, 111, 94);
    public static readonly Color Bright = Color.FromArgb(16, 185, 129);
    public static readonly Color Muted = Color.FromArgb(106, 92, 77);
    public static readonly Color Amber = Color.FromArgb(245, 158, 11);
    public static readonly Color Danger = Color.FromArgb(140, 59, 51);
}

sealed class InstallerForm : Form
{
    readonly Label statusLabel;
    readonly Label phaseLabel;
    readonly Label elapsedLabel;
    readonly Label speedValue;
    readonly Label percentValue;
    readonly Label loadedValue;
    readonly Label remainValue;
    readonly Label titleLabel;
    readonly WarmBar progressBar;
    readonly SoftButton openButton;
    readonly SoftButton reinstallButton;
    readonly Panel card;
    readonly BookIcon book;
    readonly HttpClient http = new() { Timeout = TimeSpan.FromSeconds(2) };
    readonly NotifyIcon tray;
    readonly Label versionLabel;
    readonly Label editionLabel;
    AppForm? appWindow;
    Process? engine;
    int engineGeneration;
    bool quitting;
    bool arranged;
    System.Windows.Forms.Timer? displayTimer;
    System.Windows.Forms.Timer? probeTimer;
    bool openedApp;
    bool ready;
    bool checking;
    int engineRestarts;
    DateTime lastSampleAt = DateTime.Now;
    long lastSampleBytes;
    double speedBps;
    double etaSeconds = -1;
    DateTime etaMarkedAt = DateTime.Now;
    float uiScale = 1f;

    public InstallerForm()
    {
        Text = "المجتهد";
        RightToLeft = RightToLeft.Yes;
        RightToLeftLayout = false;
        AutoScaleMode = AutoScaleMode.None;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Palette.Canvas;
        Font = AppFonts.Make(14, false);
        Icon = BrandIcon.Create();
        ClientSize = new Size(760, 508);

        book = new BookIcon();
        titleLabel = MakeLabel("المجتهد", 28, true, Palette.Ink, ContentAlignment.MiddleLeft);
        versionLabel = MakeLabel(AppVersion(), 16, true, Palette.Bright, ContentAlignment.MiddleLeft);
        versionLabel.RightToLeft = RightToLeft.No;
        editionLabel = MakeLabel("نسخة تجريبية", 12, false, Palette.Muted, ContentAlignment.MiddleLeft);
        editionLabel.RightToLeft = RightToLeft.No;
        statusLabel = MakeLabel("جاري تهيئة التطبيق", 14, false, Palette.Muted, ContentAlignment.MiddleLeft);
        card = new CardPanel();
        var cardIcon = new DownloadIcon();
        var cardTitle = MakeLabel("تشغيل المجتهد", 18, true, Palette.Ink, ContentAlignment.MiddleLeft);
        percentValue = MakeLabel("0%", 13, true, Palette.Muted, ContentAlignment.MiddleCenter);
        percentValue.BackColor = Color.FromArgb(237, 228, 214);
        phaseLabel = MakeLabel("جاري تهيئة التطبيق", 20, true, Palette.Ink, ContentAlignment.MiddleLeft);
        progressBar = new WarmBar();
        speedValue = AddStat(card, "سرعة التحميل");
        loadedValue = AddStat(card, "الحجم المحمل");
        remainValue = AddStat(card, "الحجم المتبقي");
        elapsedLabel = AddStat(card, "الوقت المتبقي");
        openButton = new SoftButton("فتح التطبيق", Palette.Bright) { Active = true };
        var quitButton = new SoftButton("إغلاق التطبيق", Palette.Muted);
        var deleteButton = new SoftButton("حذف التطبيق", Palette.Danger);
        reinstallButton = new SoftButton("إعادة التنصيب", Palette.Clay) { Active = false };
        openButton.Click += (_, _) => OpenInterface();
        quitButton.Click += (_, _) => QuitApplication();
        deleteButton.Click += (_, _) => DeleteApplication();
        reinstallButton.Click += (_, _) => ReinstallSetup();
        AcceptButton = openButton;

        Controls.Add(book);
        Controls.Add(titleLabel);
        Controls.Add(versionLabel);
        Controls.Add(editionLabel);
        Controls.Add(statusLabel);
        Controls.Add(card);
        card.Controls.Add(cardIcon);
        card.Controls.Add(cardTitle);
        card.Controls.Add(percentValue);
        card.Controls.Add(phaseLabel);
        card.Controls.Add(progressBar);
        Controls.Add(openButton);
        Controls.Add(quitButton);
        Controls.Add(deleteButton);
        Controls.Add(reinstallButton);
        arranged = true;
        LayoutHeader();

        tray = new NotifyIcon
        {
            Icon = Icon,
            Text = "المجتهد",
            Visible = false
        };
        var menu = new ContextMenuStrip { RightToLeft = RightToLeft.Yes };
        menu.Items.Add("فتح التطبيق", null, (_, _) => ShowApp());
        menu.Items.Add("نافذة التنصيب", null, (_, _) => { Show(); Activate(); });
        menu.Items.Add("إغلاق التطبيق", null, (_, _) => QuitApplication());
        tray.ContextMenuStrip = menu;
        tray.MouseClick += (_, args) =>
        {
            if (args.Button == MouseButtons.Left) ShowApp();
        };

        Shown += (_, _) =>
        {
            LayoutHeader();
            BeginSetup();
            RefreshProgress(true);
            displayTimer = new System.Windows.Forms.Timer { Interval = 10000 };
            displayTimer.Tick += (_, _) => RefreshProgress(false);
            displayTimer.Start();
            probeTimer = new System.Windows.Forms.Timer { Interval = 2000 };
            probeTimer.Tick += async (_, _) => await ProbeInterface();
            probeTimer.Start();
        };
    }

    void ApplyType()
    {
        titleLabel.Font = AppFonts.Make(22, true, uiScale);
        versionLabel.Font = AppFonts.Make(13, true, uiScale);
        editionLabel.Font = AppFonts.Make(11, false, uiScale);
        statusLabel.Font = AppFonts.Make(12, false, uiScale);
        phaseLabel.Font = AppFonts.Make(16, true, uiScale);
        percentValue.Font = AppFonts.Make(12, true, uiScale);
        foreach (var label in card.Controls.OfType<Label>())
        {
            if (label == percentValue || label == phaseLabel) continue;
            label.Font = label.Tag as string == "caption"
                ? AppFonts.Make(11, false, uiScale)
                : label.Text == "تشغيل المجتهد"
                    ? AppFonts.Make(15, true, uiScale)
                    : AppFonts.Make(14, true, uiScale);
        }
        foreach (var button in Controls.OfType<SoftButton>())
            button.Font = AppFonts.Make(13, true, uiScale);
    }

    static string AppVersion()
    {
        var version = Assembly.GetExecutingAssembly()
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion ?? "1.9.5";
        var plus = version.IndexOf('+', StringComparison.Ordinal);
        return plus > 0 ? version[..plus] : version;
    }

    void LayoutHeader()
    {
        if (!arranged || Controls.OfType<SoftButton>().Count() < 4) return;
        var raw = DeviceDpi / 96f;
        uiScale = raw < 1f ? 1f : raw > 1.15f ? 1.15f : raw;
        ApplyType();
        int S(int value) => (int)Math.Round(value * uiScale);
        if (ClientSize.Width != S(760))
            ClientSize = new Size(S(760), S(508));
        Place(versionLabel, 32, 30, 88, 24);
        Place(editionLabel, 32, 52, 120, 18);
        Place(book, 760 - 32 - 34, 30, 34, 34);
        var titleSize = TextRenderer.MeasureText(titleLabel.Text, titleLabel.Font);
        var titleWidth = titleSize.Width + S(4);
        Place(titleLabel, 760 - 32 - 34 - 8 - (int)(titleWidth / uiScale), 30, (int)(titleWidth / uiScale), 40);
        Place(statusLabel, 32, 94, 760 - 64, 24);
        Place(card, 28, 138, 760 - 56, 252);
        var inner = card.ClientSize;
        if (inner.Width < 100) return;
        if (card.Controls.OfType<DownloadIcon>().FirstOrDefault() is Control icon)
            icon.Bounds = new Rectangle(inner.Width - S(24) - S(36), S(24), S(36), S(36));
        if (card.Controls.OfType<Label>().FirstOrDefault(label => label.Text == "تشغيل المجتهد") is Control cardTitle)
            cardTitle.Bounds = new Rectangle(S(110), S(24), inner.Width - S(110) - S(72), S(32));
        percentValue.Bounds = new Rectangle(S(24), S(22), S(72), S(30));
        using (var path = RoundRect(new Rectangle(0, 0, percentValue.Width, percentValue.Height), S(8)))
            percentValue.Region = new Region(path);
        phaseLabel.Bounds = new Rectangle(S(24), S(72), inner.Width - S(48), S(56));
        progressBar.Bounds = new Rectangle(S(24), S(136), inner.Width - S(48), S(8));
        var column = (inner.Width - S(48) - S(36)) / 4f;
        var gap = S(12);
        PlaceStat(0, S(24) + (int)((column + gap) * 3), (int)column);
        PlaceStat(1, S(24) + (int)((column + gap) * 2), (int)column);
        PlaceStat(2, S(24) + (int)(column + gap), (int)column);
        PlaceStat(3, S(24), (int)column);
        var buttonWidth = (ClientSize.Width - S(56) - gap * 3) / 4;
        var buttonY = ClientSize.Height - S(36) - S(40);
        openButton.Bounds = new Rectangle(ClientSize.Width - S(28) - buttonWidth, buttonY, buttonWidth, S(40));
        Controls.OfType<SoftButton>().ElementAt(1).Bounds = new Rectangle(ClientSize.Width - S(28) - buttonWidth * 2 - gap, buttonY, buttonWidth, S(40));
        Controls.OfType<SoftButton>().ElementAt(2).Bounds = new Rectangle(ClientSize.Width - S(28) - buttonWidth * 3 - gap * 2, buttonY, buttonWidth, S(40));
        reinstallButton.Bounds = new Rectangle(S(28), buttonY, buttonWidth, S(40));
    }

    void PlaceStat(int index, int x, int width)
    {
        var captions = card.Controls.OfType<Label>().Where(label => label.Tag as string == "caption").ToArray();
        var values = new[] { speedValue, loadedValue, remainValue, elapsedLabel };
        if (index >= captions.Length) return;
        int S(int value) => (int)Math.Round(value * uiScale);
        captions[index].Bounds = new Rectangle(x, S(178), width, S(22));
        values[index].Bounds = new Rectangle(x, S(202), width, S(28));
    }

    protected override void OnDpiChanged(DpiChangedEventArgs e)
    {
        base.OnDpiChanged(e);
        LayoutHeader();
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        LayoutHeader();
    }

    protected override void WndProc(ref Message m)
    {
        if (m.Msg == Native.ActivateMessage)
        {
            if (ready) ShowApp();
            else { Show(); Activate(); }
            Native.SetForegroundWindow(Handle);
        }
        base.WndProc(ref m);
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (e.CloseReason == CloseReason.UserClosing && ready && !quitting)
        {
            e.Cancel = true;
            Hide();
            tray.Visible = true;
            return;
        }
        if (!quitting && !ready)
        {
            quitting = true;
            ShutdownServices();
        }
        displayTimer?.Stop();
        probeTimer?.Stop();
        tray.Visible = false;
        base.OnFormClosing(e);
    }

    void Place(Control control, int x, int y, int width, int height)
    {
        control.Bounds = new Rectangle(
            (int)Math.Round(x * uiScale),
            (int)Math.Round(y * uiScale),
            (int)Math.Round(width * uiScale),
            (int)Math.Round(height * uiScale));
    }

    static Label MakeLabel(string text, float size, bool bold, Color color, ContentAlignment align)
    {
        return new Label
        {
            Text = text,
            Font = AppFonts.Make(size, bold),
            ForeColor = color,
            BackColor = align == ContentAlignment.MiddleLeft ? Palette.Canvas : Color.Transparent,
            TextAlign = align,
            RightToLeft = RightToLeft.Yes,
            AutoSize = false,
            AutoEllipsis = true
        };
    }

    static Label AddStat(Control parent, string caption)
    {
        var title = MakeLabel(caption, 13, false, Palette.Muted, ContentAlignment.MiddleLeft);
        title.Tag = "caption";
        title.BackColor = Palette.Paper;
        var value = MakeLabel("—", 18, true, Palette.Ink, ContentAlignment.MiddleLeft);
        value.BackColor = Palette.Paper;
        parent.Controls.Add(title);
        parent.Controls.Add(value);
        return value;
    }

    void BeginSetup()
    {
        var choice = Path.Combine(Paths.Runtime, "web_ui", "local_source.json");
        if (File.Exists(choice) || DataAlreadyInstalled())
        {
            StartEngine();
            return;
        }
        if (CloudAlreadyStarted())
        {
            WriteSource("cloud", null);
            StartEngine();
            return;
        }
        AskSource();
    }

    bool DataAlreadyInstalled()
    {
        if (ByteCount(Paths.ModelFile) <= 1_000_000_000) return false;
        var shamela = Path.Combine(Paths.Runtime, "shamela4_data");
        if (!Directory.Exists(shamela)) return false;
        var collection = Path.Combine(Paths.Runtime, "qdrant_service", "storage", "collections", "shamela_almojtahed_8b_dense");
        if (Directory.Exists(collection)) return true;
        return ByteCount(Path.Combine(Paths.Snapshots, Paths.SnapshotName)) > 1_000_000_000;
    }

    bool CloudAlreadyStarted()
    {
        return IncompleteModelExists() || SnapshotDownloadBytes() != null;
    }

    void WriteSource(string mode, string? path)
    {
        var directory = Path.Combine(Paths.Runtime, "web_ui");
        Directory.CreateDirectory(directory);
        var payload = path == null
            ? "{\"mode\":\"" + mode + "\"}"
            : "{\"mode\":\"" + mode + "\",\"path\":\"" + path.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"}";
        File.WriteAllText(Path.Combine(directory, "local_source.json"), payload, new System.Text.UTF8Encoding(false));
    }

    void AskSource()
    {
        using var dialog = new Form
        {
            Text = "مصدر البيانات",
            RightToLeft = RightToLeft.Yes,
            RightToLeftLayout = true,
            FormBorderStyle = FormBorderStyle.FixedDialog,
            StartPosition = FormStartPosition.CenterParent,
            MaximizeBox = false,
            MinimizeBox = false,
            ClientSize = new Size(560, 230),
            Font = AppFonts.Make(14, false),
            BackColor = Palette.Canvas
        };
        var text = new Label
        {
            Text = "نموذج التضمين، والمكتبة الشاملة، وقاعدة البيانات (السنابشوت). السحابة تكمل التنصيب بالتنزيل الحالي، والمحلية تنسخها من مجلد على القرص.",
            AutoSize = false,
            TextAlign = ContentAlignment.MiddleRight,
            Bounds = new Rectangle(24, 24, 512, 110),
            ForeColor = Palette.Ink
        };
        var cloud = new Button { Text = "سحابة", DialogResult = DialogResult.Yes, Bounds = new Rectangle(300, 160, 140, 42) };
        var local = new Button { Text = "محلية", DialogResult = DialogResult.No, Bounds = new Rectangle(140, 160, 140, 42) };
        dialog.Controls.Add(text);
        dialog.Controls.Add(cloud);
        dialog.Controls.Add(local);
        dialog.AcceptButton = cloud;
        dialog.CancelButton = cloud;
        var answer = dialog.ShowDialog(this);
        if (answer == DialogResult.No)
        {
            var folder = PickLocalFolder();
            if (folder == null) return;
            WriteSource("local", folder);
        }
        else
        {
            WriteSource("cloud", null);
        }
        StartEngine();
    }

    string? PickLocalFolder()
    {
        using var dialog = new FolderBrowserDialog
        {
            Description = "اختر المجلد الذي يحتوي على نموذج التضمين والمكتبة الشاملة وقاعدة البيانات",
            UseDescriptionForTitle = true
        };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            AskSource();
            return null;
        }
        if (LocalFolderIsValid(dialog.SelectedPath)) return dialog.SelectedPath;
        var again = MessageBox.Show(
            this,
            "يلزم أن يحتوي المجلد على نموذج التضمين والمكتبة الشاملة وقاعدة البيانات. نعم لاختيار مجلد آخر، ولا للسحابة.",
            "المجلد غير مكتمل",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning,
            MessageBoxDefaultButton.Button1,
            MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign);
        if (again == DialogResult.No)
        {
            WriteSource("cloud", null);
            StartEngine();
            return null;
        }
        return PickLocalFolder();
    }

    static bool LocalFolderIsValid(string folder)
    {
        foreach (var root in new[] { folder, Path.Combine(folder, "المجتهد-محلي") })
        {
            if (ModelInFolder(root) && ShamelaInFolder(root) && DatabaseInFolder(root)) return true;
        }
        return false;
    }

    static bool ModelInFolder(string root)
    {
        foreach (var relative in new[] { "model/almojtahed-embedding-8b-Q4_K_M.gguf", "models/gguf/almojtahed-embedding-8b-Q4_K_M.gguf" })
        {
            if (ByteCount(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar))) > 1_000_000_000) return true;
        }
        return false;
    }

    static bool ShamelaInFolder(string root)
    {
        foreach (var name in new[] { "shamela", "shamela4_data" })
        {
            var path = Path.Combine(root, name);
            if (Directory.Exists(path) && Directory.EnumerateFileSystemEntries(path).Any()) return true;
        }
        return false;
    }

    static bool DatabaseInFolder(string root)
    {
        var snapshot = "shamela_almojtahed_8b_dense-2735741993374707-2026-10-15-02-17-32.snapshot";
        foreach (var relative in new[] { "database/snapshot/" + snapshot, "qdrant_service/snapshots/" + snapshot })
        {
            if (ByteCount(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar))) > 1_000_000_000) return true;
        }
        foreach (var relative in new[]
        {
            "database/storage/collections/shamela_almojtahed_8b_dense",
            "qdrant_service/storage/collections/shamela_almojtahed_8b_dense"
        })
        {
            var path = Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar));
            if (Directory.Exists(path) && Directory.EnumerateFileSystemEntries(path).Any()) return true;
        }
        return false;
    }

    void StartEngine()
    {
        var script = Path.Combine(AppContext.BaseDirectory, "launch.ps1");
        if (!File.Exists(script))
        {
            phaseLabel.Text = "تعذر تشغيل المجتهد";
            return;
        }
        var generation = ++engineGeneration;
        var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = $"-NoProfile -ExecutionPolicy Bypass -File \"{script}\"",
                WorkingDirectory = AppContext.BaseDirectory,
                UseShellExecute = false,
                CreateNoWindow = true
            },
            EnableRaisingEvents = true
        };
        process.Exited += (_, _) =>
        {
            try
            {
                if (IsDisposed) return;
                BeginInvoke(() =>
                {
                    if (generation != engineGeneration || quitting || ready) return;
                    if (engineRestarts < 8 && (DownloadStillRunning() || engineRestarts < 3))
                    {
                        engineRestarts++;
                        var phrase = DownloadStillRunning() ? "جاري تثبيت الملفات" : "جاري فتح التطبيق";
                        phaseLabel.Text = phrase;
                        statusLabel.Text = phrase;
                        Task.Delay(1500).ContinueWith(_ =>
                        {
                            try
                            {
                                if (!IsDisposed) BeginInvoke(() =>
                                {
                                    if (!quitting && !ready) StartEngine();
                                });
                            }
                            catch { }
                        });
                        return;
                    }
                    if (DownloadStillRunning()) return;
                    phaseLabel.Text = "تعذر تشغيل التطبيق";
                    statusLabel.Text = "تعذر تشغيل التطبيق";
                    if (FilesLookDamaged())
                        reinstallButton.Active = true;
                });
            }
            catch { }
        };
        try
        {
            process.Start();
            engine = process;
        }
        catch
        {
            phaseLabel.Text = "تعذر تشغيل المجتهد";
        }
    }

    async void OpenInterface()
    {
        var phrase = DownloadStillRunning() ? "جاري تثبيت الملفات" : "جاري فتح التطبيق";
        phaseLabel.Text = phrase;
        statusLabel.Text = phrase;
        if (engine == null || engine.HasExited)
            StartEngine();
        if (await InterfaceIsUp())
            ShowApp();
    }

    void ShowApp()
    {
        if (appWindow == null)
        {
            appWindow = new AppForm();
            appWindow.VisibleChanged += (_, _) => tray.Visible = ready && !Visible && appWindow is { Visible: false };
        }
        _ = appWindow.Open("http://127.0.0.1:8085/?v=1.10.543");
        tray.Visible = false;
    }

    void QuitApplication()
    {
        phaseLabel.Text = "سيتم إغلاق التطبيق";
        quitting = true;
        ShutdownServices();
        tray.Visible = false;
        Application.Exit();
    }

    void DeleteApplication()
    {
        var answer = MessageBox.Show(
            this,
            "سيتم إغلاق التطبيق وحذف بياناته.",
            "حذف التطبيق",
            MessageBoxButtons.OKCancel,
            MessageBoxIcon.Warning,
            MessageBoxDefaultButton.Button2,
            MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign);
        if (answer != DialogResult.OK) return;
        phaseLabel.Text = "سيتم إغلاق التطبيق";
        quitting = true;
        ShutdownServices();
        try { Directory.Delete(Paths.Support, true); } catch { }
        var folder = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        Process.Start(new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = $"/c timeout /t 2 /nobreak >nul & rmdir /s /q \"{folder}\"",
            CreateNoWindow = true,
            UseShellExecute = false
        });
        tray.Visible = false;
        Environment.Exit(0);
    }

    void ReinstallSetup()
    {
        if (!reinstallButton.Active) return;
        var answer = MessageBox.Show(
            this,
            "ستُعاد تهيئة التطبيق من جديد. المحادثات تبقى.",
            "إعادة التنصيب",
            MessageBoxButtons.OKCancel,
            MessageBoxIcon.Warning,
            MessageBoxDefaultButton.Button2,
            MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign);
        if (answer != DialogResult.OK) return;
        phaseLabel.Text = "جاري تهيئة التطبيق";
        reinstallButton.Active = false;
        openButton.Active = false;
        ready = false;
        speedBps = 0;
        etaSeconds = -1;
        lastSampleBytes = 0;
        ShutdownServices();
        foreach (var relative in new[]
        {
            "models/gguf",
            "qdrant_service/snapshots",
            "qdrant_service/storage/tmp",
            "qdrant_service/storage/collections",
            "shamela4_data/_git_tmp",
            "web_ui/bootstrap_status.json",
            "web_ui/local_source.json"
        })
        {
            var path = Path.Combine(Paths.Runtime, relative.Replace('/', Path.DirectorySeparatorChar));
            try
            {
                if (Directory.Exists(path)) Directory.Delete(path, true);
                else if (File.Exists(path)) File.Delete(path);
            }
            catch { }
        }
        BeginSetup();
    }

    void ShutdownServices()
    {
        engineGeneration++;
        try { if (engine is { HasExited: false }) engine.Kill(entireProcessTree: true); } catch { }
        StopOwned(Path.Combine(Paths.Support, "qdrant.pid"));
        StopOwned(Path.Combine(Paths.Support, "init.pid"));
        foreach (var port in new[] { 6333, 8085 })
        {
            foreach (var pid in Native.ListeningPids(port))
                StopPid(pid);
        }
    }

    static void StopOwned(string pidFile)
    {
        if (!File.Exists(pidFile)) return;
        if (int.TryParse(File.ReadAllText(pidFile).Trim(), out var pid))
            StopPid(pid);
    }

    static void StopPid(int pid)
    {
        if (pid <= 0 || pid == Environment.ProcessId) return;
        try
        {
            using var process = Process.GetProcessById(pid);
            var path = process.MainModule?.FileName ?? "";
            if (!path.Contains($"{Path.DirectorySeparatorChar}Al-Mujtahed{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase))
                return;
            process.Kill(entireProcessTree: true);
        }
        catch { }
    }

    void RefreshProgress(bool resetSpeed)
    {
        if (ready) return;
        var message = CurrentStatus();
        var boot = ReadBootstrap();
        if (boot?.Phase == "snapshot" && !string.IsNullOrWhiteSpace(boot.Message))
            message = boot.Message;
        if (!string.IsNullOrWhiteSpace(message))
        {
            var phrase = PublicPhase(message);
            phaseLabel.Text = phrase;
            statusLabel.Text = phrase;
        }
        var transfer = TransferState();
        var now = DateTime.Now;
        var grew = !resetSpeed && transfer.Received > lastSampleBytes;
        var delta = (now - lastSampleAt).TotalSeconds;
        if (grew && delta >= 1)
        {
            var measured = (transfer.Received - lastSampleBytes) / delta;
            if (measured >= 1) speedBps = measured;
        }
        lastSampleBytes = transfer.Received;
        lastSampleAt = now;
        var percent = DisplayedPercent(message, transfer);
        var installing = ReadBootstrap()?.Phase == "install";
        if (installing && transfer.Expected > 0)
            percent = Math.Min(100, Math.Max(transfer.Received, 0) * 100.0 / transfer.Expected);
        progressBar.Fraction = (float)(percent / 100);
        percentValue.Text = $"{(int)Math.Round(percent)}%";
        var captions = card.Controls.OfType<Label>().Where(label => label.Tag as string == "caption").ToArray();
        if (installing)
        {
            if (captions.Length > 0) captions[0].Text = "نسبة التركيب";
            for (var index = 1; index < captions.Length; index++) captions[index].Text = "";
            speedValue.Text = percentValue.Text;
            loadedValue.Text = "";
            remainValue.Text = "";
            elapsedLabel.Text = "";
        }
        else
        {
            var names = new[] { "سرعة التحميل", "الحجم المحمل", "الحجم المتبقي", "الوقت المتبقي" };
            for (var index = 0; index < captions.Length && index < names.Length; index++)
                captions[index].Text = names[index];
            speedValue.Text = SpeedText();
            loadedValue.Text = transfer.Received > 0 ? BytesText(transfer.Received) : "—";
            var remain = Math.Max(0, transfer.Expected - transfer.Received);
            remainValue.Text = transfer.Expected > 0 ? BytesText(remain) : "—";
            elapsedLabel.Text = RemainingClock(remain, grew);
        }
        var damaged = FilesLookDamaged();
        reinstallButton.Active = damaged && !DownloadStillRunning();
        if (damaged && !DownloadStillRunning())
            phaseLabel.Text = "تعذر تشغيل التطبيق";
    }

    string PublicPhase(string message)
    {
        switch (ReadBootstrap()?.Phase)
        {
            case "download":
            case "install":
            case "snapshot":
            case "local":
                return "جاري تثبيت الملفات";
        }
        if (message.Contains("تعذر", StringComparison.Ordinal) || message.Contains("تلف", StringComparison.Ordinal)
            || message.Contains("انقطاع", StringComparison.Ordinal) || message.Contains("يلزم", StringComparison.Ordinal))
            return "تعذر تشغيل التطبيق";
        if (message.Contains("فتح التطبيق", StringComparison.Ordinal) || message.Contains("الواجهة", StringComparison.Ordinal))
            return "جاري فتح التطبيق";
        var installing = message.Contains("بايثون", StringComparison.Ordinal) || message.Contains("Python", StringComparison.Ordinal)
            || message.Contains("مكتبات", StringComparison.Ordinal) || message.Contains("بيئة", StringComparison.Ordinal)
            || message.Contains("تثبيت", StringComparison.Ordinal) || message.Contains("تنزيل", StringComparison.Ordinal)
            || message.Contains("سحب", StringComparison.Ordinal) || message.Contains("نموذج", StringComparison.Ordinal)
            || message.Contains("تضمين", StringComparison.Ordinal) || message.Contains("محرك", StringComparison.Ordinal)
            || message.Contains("سنابشوت", StringComparison.Ordinal) || message.Contains("قاعدة", StringComparison.Ordinal)
            || message.Contains("Qdrant", StringComparison.Ordinal) || IncompleteModelExists();
        if (installing)
        {
            var stillWorking = message.Contains("جاري", StringComparison.Ordinal) || message.Contains("سحب", StringComparison.Ordinal)
                || message.Contains("تنزيل", StringComparison.Ordinal) || message.Contains("تثبيت", StringComparison.Ordinal);
            if (!stillWorking && (message.Contains("موجود", StringComparison.Ordinal) || message.Contains("تم تشغيل", StringComparison.Ordinal) || message.Contains("يعمل", StringComparison.Ordinal)))
                return "جاري فتح التطبيق";
            return "جاري تثبيت الملفات";
        }
        if (message.Contains("تهيئة", StringComparison.Ordinal) || message.Contains("تجهيز", StringComparison.Ordinal) || string.IsNullOrWhiteSpace(message))
            return "جاري تهيئة التطبيق";
        return "جاري فتح التطبيق";
    }

    static bool IncompleteModelExists()
    {
        var cache = Path.Combine(Paths.Runtime, "models", "gguf", ".cache", "huggingface", "download");
        return Directory.Exists(cache) && Directory.EnumerateFiles(cache, "*.incomplete").Any();
    }

    double DisplayedPercent(string message, Transfer transfer)
    {
        var phase = ReadBootstrap()?.Phase;
        if ((phase == "download" || phase == "install" || phase == "local") && transfer.Expected > 0)
            return Math.Min(90, Math.Max(transfer.Received, 0) / (double)transfer.Expected * 90);
        if (transfer.Expected > transfer.Received && transfer.Received > 0)
            return Math.Min(90, transfer.Received / (double)transfer.Expected * 90);
        if (message.Contains("بيئة بايثون", StringComparison.Ordinal)) return 8;
        if (message.Contains("مكتبات", StringComparison.Ordinal)) return 20;
        if (message.Contains("تنزيل محرك", StringComparison.Ordinal)) return 34;
        if (message.Contains("تم تشغيل Qdrant", StringComparison.Ordinal) || message.Contains("Qdrant يعمل", StringComparison.Ordinal)) return 42;
        if (message.Contains("موجود", StringComparison.Ordinal) || message.Contains("سنابشوت", StringComparison.Ordinal) || message.Contains("الشاملة", StringComparison.Ordinal)) return 88;
        if (message.Contains("الواجهة", StringComparison.Ordinal) || message.Contains("فتح التطبيق", StringComparison.Ordinal)) return 94;
        if (message.Contains("تثبيت الملفات", StringComparison.Ordinal) || message.Contains("تثبيت", StringComparison.Ordinal)) return 22;
        if (message.Contains("تهيئة", StringComparison.Ordinal) || message.Contains("تجهيز", StringComparison.Ordinal)) return 8;
        if (transfer.Expected > 0 && transfer.Received > 0)
            return Math.Min(90, transfer.Received / (double)transfer.Expected * 90);
        return 4;
    }

    void MarkReady()
    {
        ready = true;
        progressBar.Fraction = 1;
        percentValue.Text = "100%";
        speedValue.Text = SpeedText();
        var transfer = TransferState();
        if (transfer.Received > 0) loadedValue.Text = BytesText(transfer.Received);
        remainValue.Text = "0 ميجا";
        elapsedLabel.Text = "00:00:00";
        statusLabel.Text = "جاري فتح التطبيق";
        phaseLabel.Text = "جاري فتح التطبيق";
        openButton.Active = true;
        if (!openedApp)
        {
            openedApp = true;
            ShowApp();
        }
    }

    async Task<bool> InterfaceIsUp()
    {
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(1200));
            var response = await http.GetAsync("http://127.0.0.1:8085/", cts.Token);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    async Task ProbeInterface()
    {
        if (checking || ready) return;
        checking = true;
        try
        {
            if (!await InterfaceIsUp()) return;
            if (appWindow is not { PageReady: true })
            {
                openedApp = true;
                ShowApp();
            }
            openButton.Active = true;
            engineRestarts = 0;
            if (DatabaseAlreadyPresent())
            {
                MarkReady();
                return;
            }
            var phase = ReadBootstrap()?.Phase;
            if (phase is "download" or "install" or "snapshot" or "local" or "error" || FilesLookDamaged()) return;
            MarkReady();
        }
        catch { }
        finally { checking = false; }
    }

    readonly record struct Transfer(long Received, long Expected);

    Transfer TransferState()
    {
        var boot = ReadBootstrap();
        if (boot?.Phase == "local" && boot.Expected > 0)
            return new Transfer(Math.Min(Math.Max(boot.Received, 0), boot.Expected), boot.Expected);
        var modelSize = ByteCount(Paths.ModelFile);
        if (modelSize > 1_000_000_000)
        {
            var expected = ReadBootstrap()?.Expected ?? Paths.SnapshotExpected;
            if (expected <= 0) expected = Paths.SnapshotExpected;
            var phase = ReadBootstrap()?.Phase;
            if (phase == "download")
            {
                var partial = SnapshotDownloadBytes() ?? ReadBootstrap()?.Received ?? 0;
                return new Transfer(Math.Min(partial, expected), expected);
            }
            if (phase == "install")
            {
                var installed = ReadBootstrap()?.Received ?? 0;
                return new Transfer(Math.Min(Math.Max(installed, 0), expected), expected);
            }
            return new Transfer(modelSize, modelSize);
        }
        long received = ByteCount(Paths.ModelFile);
        var root = Path.Combine(Paths.Runtime, "models", "gguf");
        if (Directory.Exists(root))
        {
            foreach (var file in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories))
            {
                var name = Path.GetFileName(file);
                if (name.EndsWith(".lock", StringComparison.OrdinalIgnoreCase) || name.EndsWith(".metadata", StringComparison.OrdinalIgnoreCase))
                    continue;
                var inCache = file.Contains($"{Path.DirectorySeparatorChar}.cache{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase);
                var partial = name.EndsWith(".incomplete", StringComparison.OrdinalIgnoreCase)
                    || name.EndsWith(".partial", StringComparison.OrdinalIgnoreCase)
                    || name.Contains(".part", StringComparison.OrdinalIgnoreCase);
                if (!inCache && !partial && !name.EndsWith(".gguf", StringComparison.OrdinalIgnoreCase))
                    continue;
                received = Math.Max(received, new FileInfo(file).Length);
            }
        }
        return new Transfer(received, Math.Max(Paths.ModelExpected, received));
    }

    static long? SnapshotDownloadBytes()
    {
        var partial = Path.Combine(Paths.Snapshots, Paths.SnapshotName + ".partial");
        var finalFile = Path.Combine(Paths.Snapshots, Paths.SnapshotName);
        var partialSize = ByteCount(partial);
        if (partialSize > 0) return partialSize;
        var finalSize = ByteCount(finalFile);
        if (finalSize > 0) return finalSize;
        var cache = Path.Combine(Paths.Snapshots, ".cache", "huggingface", "download");
        if (!Directory.Exists(cache)) return null;
        long received = 0;
        foreach (var file in Directory.EnumerateFiles(cache, "*.incomplete"))
            received = Math.Max(received, new FileInfo(file).Length);
        return received > 0 ? received : null;
    }

    sealed class Bootstrap
    {
        public string Phase { get; set; } = "";
        public string Message { get; set; } = "";
        public long Expected { get; set; }
        public long Received { get; set; }
        public bool NeedsReinstall { get; set; }
    }

    static Bootstrap? ReadBootstrap()
    {
        try
        {
            if (!File.Exists(Paths.BootstrapFile)) return null;
            using var doc = JsonDocument.Parse(File.ReadAllText(Paths.BootstrapFile));
            var root = doc.RootElement;
            return new Bootstrap
            {
                Phase = root.TryGetProperty("phase", out var phase) ? phase.GetString() ?? "" : "",
                Message = root.TryGetProperty("message", out var message) ? message.GetString() ?? "" : "",
                Expected = root.TryGetProperty("expected_bytes", out var expected) ? expected.GetInt64() : 0,
                Received = root.TryGetProperty("received_bytes", out var received) ? received.GetInt64() : 0,
                NeedsReinstall = root.TryGetProperty("needs_reinstall", out var needs) && needs.ValueKind == JsonValueKind.True
            };
        }
        catch { return null; }
    }

    bool DownloadStillRunning()
    {
        var boot = ReadBootstrap();
        return boot != null && !boot.NeedsReinstall && boot.Phase is "download" or "install" or "snapshot";
    }

    static bool DatabaseAlreadyPresent()
    {
        var collection = Path.Combine(Paths.Runtime, "qdrant_service", "storage", "collections", "shamela_almojtahed_8b_dense");
        if (Directory.Exists(collection) && Directory.EnumerateFileSystemEntries(collection).Any()) return true;
        return ByteCount(Path.Combine(Paths.Snapshots, Paths.SnapshotName)) > 1_000_000_000;
    }

    bool FilesLookDamaged()
    {
        var boot = ReadBootstrap();
        if (boot?.NeedsReinstall == true || boot?.Phase == "error") return true;
        var size = ByteCount(Paths.ModelFile);
        return size > 0 && size < 1_000_000_000 && !IncompleteModelExists();
    }

    static long ByteCount(string path) => File.Exists(path) ? new FileInfo(path).Length : 0;

    string SpeedText()
    {
        if (speedBps < 1) return "—";
        if (speedBps >= 1_048_576) return (speedBps / 1_048_576d).ToString("0.00", CultureInfo.InvariantCulture) + " ميجا/ث";
        return (speedBps / 1024).ToString("0", CultureInfo.InvariantCulture) + " كيلو/ث";
    }

    static string BytesText(long bytes)
    {
        if (bytes <= 0) return "0 ميجا";
        var gb = bytes / 1_073_741_824d;
        if (gb >= 1) return gb.ToString("0.00", CultureInfo.InvariantCulture) + " جيجا";
        return (bytes / 1_048_576d).ToString("0", CultureInfo.InvariantCulture) + " ميجا";
    }

    string RemainingClock(long remain, bool reset)
    {
        if (remain <= 0) return "00:00:00";
        if (speedBps < 1) return "—";
        var now = DateTime.Now;
        if (reset || etaSeconds < 0)
        {
            etaSeconds = remain / speedBps;
            etaMarkedAt = now;
        }
        return Clock(Math.Max(0, etaSeconds - (now - etaMarkedAt).TotalSeconds));
    }

    static string Clock(double interval)
    {
        var total = Math.Max(0, (int)interval);
        return $"{total / 3600:00}:{(total % 3600) / 60:00}:{total % 60:00}";
    }

    static string CurrentStatus()
    {
        try { return File.Exists(Paths.StatusFile) ? File.ReadAllText(Paths.StatusFile).Trim() : ""; }
        catch { return ""; }
    }

    static GraphicsPath RoundRect(Rectangle bounds, int radius)
    {
        var path = new GraphicsPath();
        int d = Math.Max(1, radius * 2);
        path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
        path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
        path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }
}

sealed class AppForm : Form
{
    readonly Microsoft.Web.WebView2.WinForms.WebView2 web = new() { Dock = DockStyle.Fill };
    Microsoft.Web.WebView2.Core.CoreWebView2Environment? environment;
    bool wired;
    string? pendingUrl;
    public bool PageReady { get; private set; }

    internal const string HideScrollbarsScript = @"
(() => {
  const hide = () => {
    const style = document.createElement('style');
    style.textContent = 'html,body,*{scrollbar-width:none !important;-ms-overflow-style:none !important}html::-webkit-scrollbar,body::-webkit-scrollbar,*::-webkit-scrollbar{width:0 !important;height:0 !important;display:none !important;background:transparent !important}';
    (document.head || document.documentElement).appendChild(style);
  };
  if (document.head) hide();
  else document.addEventListener('DOMContentLoaded', hide);
})();
";

    public AppForm()
    {
        Text = "المجتهد";
        Icon = BrandIcon.Create();
        StartPosition = FormStartPosition.Manual;
        WindowState = FormWindowState.Normal;
        MinimumSize = new Size(900, 640);
        BackColor = Palette.Canvas;
        web.DefaultBackgroundColor = Palette.Canvas;
        Controls.Add(web);
        FitDesktop();
    }

    void FitDesktop()
    {
        var screen = Screen.FromPoint(Cursor.Position);
        var area = screen?.WorkingArea ?? Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1200, 800);
        WindowState = FormWindowState.Normal;
        Bounds = area;
    }

    public async Task Open(string url)
    {
        pendingUrl = url;
        try
        {
            if (web.CoreWebView2 == null)
            {
                var folder = Path.Combine(Paths.Support, "webview");
                Directory.CreateDirectory(folder);
                // مسح كاش الصفحات والسكريبتات فقط. بيانات الموقع والمحادثات والإعدادات تبقى في مجلدات أخرى.
                foreach (var cacheDir in new[]
                {
                    Path.Combine(folder, "EBWebView", "Default", "Cache"),
                    Path.Combine(folder, "EBWebView", "Default", "Code Cache"),
                    Path.Combine(folder, "EBWebView", "Default", "GPUCache"),
                    Path.Combine(folder, "EBWebView", "GrShaderCache"),
                    Path.Combine(folder, "EBWebView", "ShaderCache")
                })
                {
                    try { if (Directory.Exists(cacheDir)) Directory.Delete(cacheDir, true); } catch { }
                }
                web.DefaultBackgroundColor = Palette.Canvas;
                var options = new Microsoft.Web.WebView2.Core.CoreWebView2EnvironmentOptions("--disable-gpu --disable-gpu-compositing");
                environment = await Microsoft.Web.WebView2.Core.CoreWebView2Environment.CreateAsync(null, folder, options);
                await web.EnsureCoreWebView2Async(environment);
            }
            if (!wired && web.CoreWebView2 != null)
            {
                wired = true;
                web.CoreWebView2.Settings.IsStatusBarEnabled = false;
                web.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
                await web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(HideScrollbarsScript);
                web.CoreWebView2.WebMessageReceived += (_, e) =>
                {
                    string text = "";
                    try { text = e.TryGetWebMessageAsString() ?? ""; } catch { }
                    if (!text.Contains("chooseFolder")) return;
                    try
                    {
                        BeginInvoke((Action)(() =>
                        {
                            string picked = "";
                            using (var dialog = new FolderBrowserDialog
                            {
                                Description = "اختر مجلد المكتبة الشاملة (الذي يحتوي مجلد database)",
                                ShowNewFolderButton = false
                            })
                            {
                                if (dialog.ShowDialog(this) == DialogResult.OK)
                                    picked = dialog.SelectedPath ?? "";
                            }
                            try
                            {
                                web.CoreWebView2?.PostWebMessageAsJson(
                                    "{\"almujtahedFolder\":" + JsonSerializer.Serialize(picked) + "}");
                            }
                            catch { }
                        }));
                    }
                    catch { }
                };
                web.CoreWebView2.NavigationStarting += (_, args) =>
                {
                    if (args.IsUserInitiated && !IsLocal(args.Uri))
                    {
                        args.Cancel = true;
                        OpenExternal(args.Uri);
                    }
                };
                web.CoreWebView2.NewWindowRequested += (_, args) => OpenRequestedWindow(environment, args);
                web.CoreWebView2.NavigationCompleted += (_, args) =>
                {
                    var failed = !args.IsSuccess && args.WebErrorStatus is
                        Microsoft.Web.WebView2.Core.CoreWebView2WebErrorStatus.CannotConnect
                        or Microsoft.Web.WebView2.Core.CoreWebView2WebErrorStatus.ConnectionAborted
                        or Microsoft.Web.WebView2.Core.CoreWebView2WebErrorStatus.ConnectionReset
                        or Microsoft.Web.WebView2.Core.CoreWebView2WebErrorStatus.Disconnected
                        or Microsoft.Web.WebView2.Core.CoreWebView2WebErrorStatus.HostNameNotResolved
                        or Microsoft.Web.WebView2.Core.CoreWebView2WebErrorStatus.ServerUnreachable
                        or Microsoft.Web.WebView2.Core.CoreWebView2WebErrorStatus.Timeout;
                    if (!failed)
                    {
                        var scheme = web.Source?.Scheme;
                        if (args.IsSuccess && (scheme == "http" || scheme == "https"))
                            PageReady = true;
                        return;
                    }
                    PageReady = false;
                    web.CoreWebView2.NavigateToString(
                        "<html dir='rtl'><body style='margin:0;background:#f1e9dc;color:#2a221a;font-family:Segoe UI,Tahoma,sans-serif;display:flex;height:100vh;align-items:center;justify-content:center;font-size:22px'>جاري فتح التطبيق</body></html>");
                };
            }
            if (!Visible)
            {
                FitDesktop();
                Show();
            }
            Activate();
            if (!string.IsNullOrEmpty(pendingUrl))
                web.CoreWebView2?.Navigate(pendingUrl);
        }
        catch
        {
            if (Visible) Hide();
            MessageBox.Show(
                this,
                "يلزم مكوّن WebView2 من مايكروسوفت لفتح نافذة التطبيق. سيُفتح رابط تثبيته.",
                "المجتهد",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information,
                MessageBoxDefaultButton.Button1,
                MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign);
            OpenExternal("https://go.microsoft.com/fwlink/p/?LinkId=2124703");
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        if (e.CloseReason == CloseReason.UserClosing)
        {
            e.Cancel = true;
            SaveBounds();
            Hide();
        }
        base.OnFormClosing(e);
    }

    protected override void OnResizeEnd(EventArgs e)
    {
        base.OnResizeEnd(e);
        SaveBounds();
    }

    void SaveBounds()
    {
        if (WindowState != FormWindowState.Normal) return;
        var path = Path.Combine(Paths.Support, "app-window.txt");
        try { File.WriteAllText(path, $"{Bounds.X},{Bounds.Y},{Bounds.Width},{Bounds.Height}"); } catch { }
    }

    internal static bool IsLocal(string raw)
    {
        if (!Uri.TryCreate(raw, UriKind.Absolute, out var uri)) return true;
        if (uri.Scheme is "about" or "blob" or "data") return true;
        return uri.Host is "localhost" or "127.0.0.1";
    }

    internal static void OpenRequestedWindow(Microsoft.Web.WebView2.Core.CoreWebView2Environment? environment, Microsoft.Web.WebView2.Core.CoreWebView2NewWindowRequestedEventArgs args)
    {
        if (!IsLocal(args.Uri))
        {
            args.Handled = true;
            OpenExternal(args.Uri);
            return;
        }
        if (environment == null)
        {
            args.Handled = true;
            return;
        }
        var deferral = args.GetDeferral();
        var popup = new ReadingForm(environment);
        popup.Show();
        _ = popup.Attach(args, deferral);
    }

    internal static void OpenExternal(string url)
    {
        try
        {
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
        catch { }
    }
}

sealed class ReadingForm : Form
{
    readonly Microsoft.Web.WebView2.WinForms.WebView2 web = new() { Dock = DockStyle.Fill };
    readonly Microsoft.Web.WebView2.Core.CoreWebView2Environment environment;

    public ReadingForm(Microsoft.Web.WebView2.Core.CoreWebView2Environment environment)
    {
        this.environment = environment;
        Text = "قراءة";
        Icon = BrandIcon.Create();
        StartPosition = FormStartPosition.Manual;
        WindowState = FormWindowState.Normal;
        MinimumSize = new Size(480, 680);
        BackColor = Palette.Canvas;
        web.DefaultBackgroundColor = Palette.Canvas;
        Controls.Add(web);
        FitA4();
    }

    void FitA4()
    {
        var screen = Screen.FromPoint(Cursor.Position);
        var area = screen?.WorkingArea ?? Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1200, 800);
        const int margin = 24;
        var height = Math.Max(MinimumSize.Height, area.Height - margin * 2);
        var width = (int)Math.Round(height * 210d / 297d * 2);
        var maxWidth = area.Width - margin * 2;
        if (width > maxWidth) width = maxWidth;
        WindowState = FormWindowState.Normal;
        Bounds = new Rectangle(
            area.X + (area.Width - width) / 2,
            area.Y + (area.Height - height) / 2,
            width,
            height);
    }

    public async Task Attach(Microsoft.Web.WebView2.Core.CoreWebView2NewWindowRequestedEventArgs args, Microsoft.Web.WebView2.Core.CoreWebView2Deferral deferral)
    {
        try
        {
            await web.EnsureCoreWebView2Async(environment);
            await web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(AppForm.HideScrollbarsScript);
            web.CoreWebView2.DocumentTitleChanged += (_, _) =>
            {
                var title = web.CoreWebView2.DocumentTitle;
                if (!string.IsNullOrWhiteSpace(title) && title != "about:blank") Text = title;
            };
            web.CoreWebView2.NewWindowRequested += (_, next) => AppForm.OpenRequestedWindow(environment, next);
            web.CoreWebView2.NavigationStarting += (_, navigation) =>
            {
                if (navigation.IsUserInitiated && !AppForm.IsLocal(navigation.Uri))
                {
                    navigation.Cancel = true;
                    AppForm.OpenExternal(navigation.Uri);
                }
            };
            args.NewWindow = web.CoreWebView2;
            args.Handled = true;
        }
        catch
        {
            args.Handled = true;
            Close();
        }
        finally
        {
            deferral.Complete();
        }
    }
}

sealed class CardPanel : Panel
{
    public CardPanel()
    {
        BackColor = Palette.Paper;
        DoubleBuffered = true;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        var rect = new Rectangle(0, 0, Width - 1, Height - 1);
        using var path = Rounded(rect, 16);
        using var pen = new Pen(Palette.Line);
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        e.Graphics.DrawPath(pen, path);
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        using var path = Rounded(new Rectangle(0, 0, Width, Height), 16);
        Region = new Region(path);
    }

    static GraphicsPath Rounded(Rectangle bounds, int radius)
    {
        var path = new GraphicsPath();
        int d = radius * 2;
        path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
        path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
        path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }
}

sealed class WarmBar : Control
{
    float fraction;
    public float Fraction
    {
        get => fraction;
        set { fraction = Math.Clamp(value, 0, 1); Invalidate(); }
    }

    public WarmBar()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
        Height = 8;
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        var track = ClientRectangle;
        FillRound(g, track, Palette.Line);
        if (fraction <= 0) return;
        int width = (int)Math.Round(track.Width * fraction);
        width = Math.Max(track.Height, width);
        var fill = new Rectangle(track.Right - width, 0, width, track.Height);
        using var brush = new LinearGradientBrush(fill, Palette.Amber, Palette.Bright, LinearGradientMode.Horizontal);
        FillRound(g, fill, brush);
    }

    static void FillRound(Graphics g, Rectangle rect, Color color)
    {
        using var brush = new SolidBrush(color);
        FillRound(g, rect, brush);
    }

    static void FillRound(Graphics g, Rectangle rect, Brush brush)
    {
        using var path = new GraphicsPath();
        int d = Math.Max(1, rect.Height);
        path.AddArc(rect.X, rect.Y, d, d, 90, 180);
        path.AddArc(rect.Right - d, rect.Y, d, d, 270, 180);
        path.CloseFigure();
        g.FillPath(brush, path);
    }
}

sealed class SoftButton : Control, IButtonControl
{
    readonly Color tint;
    bool active = true;
    public DialogResult DialogResult { get; set; }
    public bool Active
    {
        get => active;
        set { active = value; Invalidate(); }
    }

    public SoftButton(string text, Color tint)
    {
        this.tint = tint;
        Text = text;
        Font = AppFonts.Make(16, true);
        Cursor = Cursors.Hand;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
        Height = 40;
    }

    public void NotifyDefault(bool value) { }
    public void PerformClick() { if (active) OnClick(EventArgs.Empty); }

    protected override void OnClick(EventArgs e)
    {
        if (active) base.OnClick(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        int fillAlpha = active ? 36 : 14;
        int textAlpha = active ? 255 : 97;
        using var path = new GraphicsPath();
        var rect = new Rectangle(0, 0, Width - 1, Height - 1);
        int d = 12;
        path.AddArc(rect.X, rect.Y, d, d, 180, 90);
        path.AddArc(rect.Right - d, rect.Y, d, d, 270, 90);
        path.AddArc(rect.Right - d, rect.Bottom - d, d, d, 0, 90);
        path.AddArc(rect.X, rect.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        using var brush = new SolidBrush(Color.FromArgb(fillAlpha, tint));
        g.FillPath(brush, path);
        TextRenderer.DrawText(g, Text, Font, rect, Color.FromArgb(textAlpha, tint),
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.RightToLeft);
    }
}

sealed class BookIcon : Control
{
    public BookIcon()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.SupportsTransparentBackColor, true);
        BackColor = Palette.Canvas;
        Size = new Size(34, 34);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        using var pen = new Pen(Palette.Bright, 2.2f) { LineJoin = LineJoin.Round };
        var cover = new Rectangle(5, 4, Width - 12, Height - 8);
        g.DrawRectangle(pen, cover);
        g.DrawLine(pen, cover.X + 6, cover.Y, cover.X + 6, cover.Bottom);
    }
}

sealed class DownloadIcon : Control
{
    public DownloadIcon()
    {
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.OptimizedDoubleBuffer, true);
        BackColor = Palette.Paper;
        Size = new Size(36, 36);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        using var brush = new SolidBrush(Color.FromArgb(36, Palette.Amber));
        g.FillRectangle(brush, ClientRectangle);
        using var pen = new Pen(Palette.Amber, 1.8f) { StartCap = LineCap.Round, EndCap = LineCap.Round };
        g.DrawLine(pen, Width / 2f, 9, Width / 2f, Height - 12);
        g.DrawLine(pen, Width / 2f - 5, Height - 17, Width / 2f, Height - 12);
        g.DrawLine(pen, Width / 2f + 5, Height - 17, Width / 2f, Height - 12);
        g.DrawArc(pen, 8, 8, Width - 16, Height - 16, 20, 140);
    }
}

static class BrandIcon
{
    public static Icon Create()
    {
        using var bitmap = new Bitmap(32, 32);
        using (var g = Graphics.FromImage(bitmap))
        {
            g.Clear(Palette.Bright);
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using var pen = new Pen(Color.White, 2);
            g.DrawRectangle(pen, 7, 6, 18, 20);
            g.DrawLine(pen, 12, 6, 12, 26);
        }
        return Icon.FromHandle(bitmap.GetHicon());
    }
}
