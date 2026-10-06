from komicove_app.launcher import main


def check_assets():
    import tkinter as tk
    from PIL import Image, ImageTk
    import komicove_app.runtime as runtime

    root = tk.Tk()
    root.withdraw()
    runtime.load_icons()
    logo = ImageTk.PhotoImage(Image.open(runtime.resource_path("komicovelogo.png")))
    missing = [name for name, icon in runtime.ICONS.items() if icon is None]
    root.destroy()
    if missing or not logo:
        raise SystemExit("Missing icons: " + ", ".join(missing))
    print("Komicove assets OK")


def check_ai():
    from PIL import Image
    from komicove_app.guided import DetectionResult
    from komicove_app.guided_ai import LocalPanelAI

    provider = LocalPanelAI.available()
    if provider is None:
        raise SystemExit('Missing local AI model')
    try:
        with Image.new('RGB', (200, 300), 'white') as image:
            provider.detect(image, DetectionResult(((0., 0., 1., 1.),), True, .3, 'whole_page'))
        if provider._session is None or provider._disabled:
            raise SystemExit('Local AI inference failed')
        print('Komicove local AI OK')
    finally:
        provider.close()


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--check-assets"]:
        check_assets()
    elif sys.argv[1:] == ["--check-ai"]:
        check_ai()
    else:
        main()
