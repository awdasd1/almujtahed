using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32;

namespace AlMujtahed.Setup;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (args.Any(arg => arg == "--uninstall"))
        {
            Application.Run(new UninstallForm());
            return;
        }
        var extractOnly = args.Any(arg => arg == "--extract-only");
        var folder = args.FirstOrDefault(arg => arg != "--extract-only" && arg != "--setup");
        if (!string.IsNullOrWhiteSpace(folder))
        {
            try
            {
                Installer.Extract(folder, null);
                Installer.EnsureInstalledIntegration(folder);
                if (!extractOnly) Installer.Launch(folder);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex);
                Environment.ExitCode = 1;
            }
            return;
        }
        // مثبّت بنفس نسخة ما على الجهاز؟ شغّل التطبيق مباشرة بلا نافذة تنصيب.
        var existing = Installer.FindExisting();
        if (!extractOnly && !args.Any(arg => arg == "--setup")
            && existing is { } found && found.version == Installer.CurrentVersion)
        {
            // حتى لو كانت النسخة مثبتة، نصلح الاختصارات وقيد التطبيقات المثبتة
            // عند كل تشغيل للمثبّت؛ فقد تكون نسخة سابقة ثُبّتت قبل اكتمال التسجيل.
            Installer.EnsureInstalledIntegration(found.folder);
            try { Installer.Launch(found.folder); return; }
            catch { /* نكمل إلى نافذة التنصيب */ }
        }
        Application.Run(new SetupForm(existing));
    }
}

static class Installer
{
    const string MarkerName = "almujtahed-setup-info.txt";

    public static string DefaultFolder => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Programs", "المجتهد");

    public static string CurrentVersion =>
        Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "";

    public static (string folder, string version)? FindExisting()
    {
        var candidates = new List<string> { DefaultFolder };
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(UninstallKeyPath);
            if (key?.GetValue("InstallLocation") is string registered && registered.Length > 0)
                candidates.Insert(0, registered);
        }
        catch { }

        foreach (var folder in candidates.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!File.Exists(Path.Combine(folder, "AlMujtahed.exe"))) continue;
            var marker = Path.Combine(folder, MarkerName);
            var version = "";
            try { version = File.Exists(marker) ? File.ReadAllText(marker).Trim() : ""; } catch { }
            return (folder, version);
        }
        return null;
    }

    public static void WriteMarker(string folder)
    {
        try { File.WriteAllText(Path.Combine(folder, MarkerName), CurrentVersion); } catch { }
    }

    public static void EnsureInstalledIntegration(string folder)
    {
        WriteMarker(folder);
        EnsureIconFile(folder);
        CreateShortcuts(folder);
        RegisterUninstallEntry(folder);
    }

    static string IconPath(string folder) => Path.Combine(folder, "app.ico");

    static void EnsureIconFile(string folder)
    {
        var iconPath = IconPath(folder);
        if (File.Exists(iconPath)) return;
        try
        {
            var source = Environment.ProcessPath;
            if (string.IsNullOrWhiteSpace(source)) return;
            using var icon = Icon.ExtractAssociatedIcon(source);
            if (icon == null) return;
            using var stream = File.Create(iconPath);
            icon.Save(stream);
        }
        catch { }
    }

    public static void CreateShortcuts(string folder)
    {
        var exe = Path.Combine(folder, "AlMujtahed.exe");
        var iconPath = File.Exists(IconPath(folder)) ? IconPath(folder) : exe;
        var links = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "المجتهد.lnk"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "المجتهد.lnk")
        };
        foreach (var link in links)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(link)!);
                CreateShellShortcut(link, exe, folder, iconPath);
            }
            catch
            {
                try { CreateWScriptShortcut(link, exe, folder, iconPath); } catch { }
            }
        }
    }

    static void CreateShellShortcut(string linkPath, string targetPath, string workingDirectory, string iconPath)
    {
        var link = (IShellLinkW)new ShellLink();
        link.SetDescription("المجتهد — منظومة البحث التراثي");
        link.SetPath(targetPath);
        link.SetWorkingDirectory(workingDirectory);
        link.SetIconLocation(iconPath, 0);
        link.SetShowCmd(1);
        var file = (IPersistFile)link;
        file.Save(linkPath, true);
        Marshal.FinalReleaseComObject(file);
    }

    static void CreateWScriptShortcut(string linkPath, string targetPath, string workingDirectory, string iconPath)
    {
        dynamic shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell")!)!;
        dynamic shortcut = shell.CreateShortcut(linkPath);
        shortcut.TargetPath = targetPath;
        shortcut.WorkingDirectory = workingDirectory;
        shortcut.IconLocation = iconPath + ",0";
        shortcut.Description = "المجتهد — منظومة البحث التراثي";
        shortcut.Save();
    }

    [ComImport]
    [Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink
    {
    }

    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("000214F9-0000-0000-C000-000000000046")]
    interface IShellLinkW
    {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cchMaxPath, IntPtr pfd, uint fFlags);
        void GetIDList(out IntPtr ppidl);
        void SetIDList(IntPtr pidl);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszName, int cchMaxName);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszDir, int cchMaxPath);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszArgs, int cchMaxPath);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
        void GetHotkey(out short pwHotkey);
        void SetHotkey(short wHotkey);
        void GetShowCmd(out int piShowCmd);
        void SetShowCmd(int iShowCmd);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszIconPath, int cchIconPath, out int piIcon);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, uint dwReserved);
        void Resolve(IntPtr hwnd, uint fFlags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
    }

    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("0000010B-0000-0000-C000-000000000046")]
    interface IPersistFile
    {
        void GetClassID(out Guid pClassID);
        [PreserveSig]
        int IsDirty();
        void Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, uint dwMode);
        void Save([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, [MarshalAs(UnmanagedType.Bool)] bool fRemember);
        void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string pszFileName);
        void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string ppszFileName);
    }

    const string UninstallKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\AlMujtahed";

    public static void RegisterUninstallEntry(string folder)
    {
        try
        {
            using var key = Registry.CurrentUser.CreateSubKey(UninstallKeyPath);
            key.SetValue("DisplayName", "المجتهد");
            key.SetValue("DisplayVersion", CurrentVersion);
            key.SetValue("Publisher", "المجتهد");
            key.SetValue("InstallLocation", folder);
            var iconPath = File.Exists(IconPath(folder)) ? IconPath(folder) : Path.Combine(folder, "AlMujtahed.exe");
            key.SetValue("DisplayIcon", $"\"{iconPath}\",0");
            key.SetValue("InstallDate", DateTime.Now.ToString("yyyyMMdd"));
            // ملف الإلغاء يعيش داخل مجلد التثبيت نفسه، لا عند ملف التنزيلات
            // الذي قد يحذفه المستخدم فينكسر إلغاء التثبيت من الإعدادات.
            var uninstaller = Path.Combine(folder, "إلغاء تثبيت المجتهد.exe");
            var setupExe = Environment.ProcessPath ?? "";
            try
            {
                if (setupExe.Length > 0 &&
                    !string.Equals(Path.GetFullPath(setupExe), Path.GetFullPath(uninstaller), StringComparison.OrdinalIgnoreCase) &&
                    (!File.Exists(uninstaller) ||
                     FileVersionInfo.GetVersionInfo(uninstaller).FileVersion != FileVersionInfo.GetVersionInfo(setupExe).FileVersion))
                    File.Copy(setupExe, uninstaller, true);
            }
            catch { uninstaller = setupExe; }
            key.SetValue("UninstallString", $"\"{uninstaller}\" --uninstall");
            key.SetValue("NoModify", 1, RegistryValueKind.DWord);
            key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
        }
        catch { }
    }

    public static void UnregisterUninstallEntry()
    {
        try { Registry.CurrentUser.DeleteSubKeyTree(UninstallKeyPath, false); } catch { }
    }

    public static void RemoveShortcuts()
    {
        var links = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                @"Microsoft\Windows\Start Menu\Programs", "المجتهد.lnk"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "المجتهد.lnk")
        };
        foreach (var link in links)
        {
            try { if (File.Exists(link)) File.Delete(link); } catch { }
        }
    }

    public static void Extract(string folder, IProgress<int>? progress)
    {
        var destination = Path.GetFullPath(folder);
        Directory.CreateDirectory(destination);
        using var resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")
            ?? throw new InvalidOperationException("تعذر العثور على ملفات التطبيق داخل المثبّت");
        using var archive = new ZipArchive(resource, ZipArchiveMode.Read);
        var entries = archive.Entries;
        var total = Math.Max(1, entries.Count);
        var root = Path.GetFullPath(destination + Path.DirectorySeparatorChar);
        for (var index = 0; index < entries.Count; index++)
        {
            var entry = entries[index];
            var relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
            if (string.IsNullOrWhiteSpace(relative)) continue;
            var target = Path.GetFullPath(Path.Combine(destination, relative));
            if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("مسار داخل الحزمة غير مقبول");
            if (string.IsNullOrEmpty(entry.Name))
            {
                Directory.CreateDirectory(target);
            }
            else
            {
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                entry.ExtractToFile(target, overwrite: true);
            }
            progress?.Report((index + 1) * 100 / total);
        }
    }

    public static void Launch(string folder)
    {
        var exe = Path.Combine(Path.GetFullPath(folder), "AlMujtahed.exe");
        Process.Start(new ProcessStartInfo(exe)
        {
            WorkingDirectory = Path.GetDirectoryName(exe)!,
            UseShellExecute = true
        });
    }
}

sealed class SetupForm : Form
{
    readonly TextBox pathBox = new() { RightToLeft = RightToLeft.No };
    readonly Button browse = new() { Text = "استعراض" };
    readonly Button install = new() { Text = "تثبيت" };
    readonly ProgressBar bar = new() { Minimum = 0, Maximum = 100 };
    readonly Label status = new() { Text = "اختر المجلد الذي تُفك فيه ملفات التطبيق", AutoSize = false };

    public SetupForm((string folder, string version)? existing = null)
    {
        Text = "تثبيت المجتهد";
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(560, 210);
        RightToLeft = RightToLeft.Yes;
        RightToLeftLayout = true;
        Font = new Font("Segoe UI", 12);
        BackColor = Color.FromArgb(241, 233, 220);

        var title = new Label
        {
            Text = "المجتهد",
            Font = new Font(Font, FontStyle.Bold),
            AutoSize = true,
            ForeColor = Color.FromArgb(42, 34, 26),
            Location = new Point(24, 18)
        };
        status.ForeColor = Color.FromArgb(106, 92, 77);
        status.Location = new Point(24, 52);
        status.Size = new Size(512, 28);
        pathBox.Location = new Point(140, 92);
        pathBox.Size = new Size(396, 32);
        pathBox.Text = Installer.DefaultFolder;
        if (existing is { } found)
        {
            pathBox.Text = found.folder;
            install.Text = found.version == Installer.CurrentVersion ? "إعادة التثبيت" : "تحديث";
            status.Text = found.version == Installer.CurrentVersion
                ? "التطبيق مثبّت بهذه النسخة — يمكنك إعادة تثبيته أو تشغيله من قائمة ابدأ"
                : "توجد نسخة أقدم مثبّتة — التحديث يستبدل ملفات التطبيق ويبقي بياناتك";
        }
        browse.Location = new Point(24, 90);
        browse.Size = new Size(104, 34);
        install.Location = new Point(24, 142);
        install.Size = new Size(120, 40);
        bar.Location = new Point(160, 152);
        bar.Size = new Size(376, 18);
        Controls.AddRange(new Control[] { title, status, pathBox, browse, install, bar });
        browse.Click += (_, _) => ChooseFolder();
        install.Click += async (_, _) => await Install();
        AcceptButton = install;
    }

    void ChooseFolder()
    {
        using var dialog = new FolderBrowserDialog
        {
            Description = "اختر مجلد تثبيت المجتهد",
            UseDescriptionForTitle = true,
            SelectedPath = pathBox.Text
        };
        if (dialog.ShowDialog(this) == DialogResult.OK)
            pathBox.Text = dialog.SelectedPath;
    }

    async Task Install()
    {
        var folder = pathBox.Text.Trim();
        if (folder.Length == 0) return;
        install.Enabled = false;
        browse.Enabled = false;
        status.Text = "جاري فك الملفات...";
        var progress = new Progress<int>(value => bar.Value = value);
        try
        {
            await Task.Run(() => Installer.Extract(folder, progress));
            Installer.EnsureInstalledIntegration(folder);
            status.Text = "اكتمل التثبيت";
            Installer.Launch(folder);
            Close();
        }
        catch (Exception ex)
        {
            status.Text = "تعذر فك الملفات";
            MessageBox.Show(this, ex.Message, "تثبيت المجتهد", MessageBoxButtons.OK, MessageBoxIcon.Warning,
                MessageBoxDefaultButton.Button1, MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign);
            install.Enabled = true;
            browse.Enabled = true;
        }
    }
}

sealed class UninstallForm : Form
{
    public UninstallForm()
    {
        Text = "إلغاء تثبيت المجتهد";
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(460, 150);
        RightToLeft = RightToLeft.Yes;
        RightToLeftLayout = true;
        Font = new Font("Segoe UI", 12);
        BackColor = Color.FromArgb(241, 233, 220);
        var label = new Label
        {
            Text = "سيُحذف تطبيق المجتهد واختصاراته من هذا الجهاز. بيانات التطبيق في AppData تُحذف أيضًا من داخل التطبيق نفسه (زر حذف التطبيق) إن أردتها.",
            AutoSize = false,
            Location = new Point(24, 20),
            Size = new Size(412, 56),
            ForeColor = Color.FromArgb(42, 34, 26)
        };
        var ok = new Button { Text = "إلغاء التثبيت", Location = new Point(24, 92), Size = new Size(140, 38) };
        var cancel = new Button { Text = "تراجع", Location = new Point(176, 92), Size = new Size(110, 38), DialogResult = DialogResult.Cancel };
        ok.Click += (_, _) => DoUninstall();
        Controls.AddRange(new Control[] { label, ok, cancel });
        CancelButton = cancel;
    }

    void DoUninstall()
    {
        var existing = Installer.FindExisting();
        Installer.RemoveShortcuts();
        Installer.UnregisterUninstallEntry();
        if (existing is { } found)
        {
            try { Directory.Delete(found.folder, true); } catch { }
            // إن كان ملف الإلغاء نفسه داخل المجلد بقيت بقايا مقفلة أثناء
            // تشغيله، فتُحذف بعملية منفصلة بعد خروجه.
            if (Directory.Exists(found.folder))
            {
                try
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = "cmd.exe",
                        Arguments = $"/c ping -n 4 127.0.0.1 >nul & rmdir /s /q \"{found.folder}\"",
                        CreateNoWindow = true,
                        UseShellExecute = false,
                        WindowStyle = ProcessWindowStyle.Hidden
                    });
                }
                catch { }
            }
        }
        MessageBox.Show(this, "تم إلغاء تثبيت المجتهد.", "المجتهد", MessageBoxButtons.OK, MessageBoxIcon.Information,
            MessageBoxDefaultButton.Button1, MessageBoxOptions.RtlReading | MessageBoxOptions.RightAlign);
        Close();
    }
}
