using System.Runtime.InteropServices;
using Windows.ApplicationModel.DataTransfer;
using Windows.Foundation;
using Windows.Storage;
using WinRT;

namespace Almoghni;

static class NativeShare
{
    static readonly Guid DataTransferManagerIid = Guid.Parse("a5caee9b-8708-49d1-8d36-67d25a8da00c");

    [ComImport]
    [Guid("3A3DCD6C-3EAB-43DC-BCDE-45671CE800C8")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IDataTransferManagerInterop
    {
        IntPtr GetForWindow(IntPtr appWindow, ref Guid riid);
        void ShowShareUIForWindow(IntPtr appWindow);
    }

    public static void Show(IntPtr hwnd, string title, string text, string? filePath)
    {
        var interop = DataTransferManager.As<IDataTransferManagerInterop>();
        var iid = DataTransferManagerIid;
        var manager = MarshalInterface<DataTransferManager>.FromAbi(interop.GetForWindow(hwnd, ref iid));
        TypedEventHandler<DataTransferManager, DataRequestedEventArgs>? handler = null;
        handler = (_, args) =>
        {
            try
            {
                var data = args.Request.Data;
                data.Properties.Title = string.IsNullOrWhiteSpace(title) ? "المغني" : title;
                if (!string.IsNullOrWhiteSpace(text)) data.SetText(text);
                if (!string.IsNullOrWhiteSpace(filePath) && File.Exists(filePath))
                {
                    var file = StorageFile.GetFileFromPathAsync(filePath).AsTask().GetAwaiter().GetResult();
                    data.SetStorageItems(new IStorageItem[] { file });
                }
            }
            finally
            {
                if (handler != null) manager.DataRequested -= handler;
            }
        };
        manager.DataRequested += handler;
        interop.ShowShareUIForWindow(hwnd);
    }
}
