# my-first-geo-project
Exercise 2: Your First Repository

## PDF Reader/Writer GUI

This project now includes a desktop PDF reader/writer with signature capture:

- App file: src/pdf_reader_app.py
- Features: open PDF, navigate pages, zoom, rotate, search, add text stamp, draw signature, stamp signature, certificate-based digital signing, save edited PDF

### Run Locally (Linux/macOS/Windows)

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python src/pdf_reader_app.py
```

### Quick Test Checklist

1. Open a sample PDF.
2. Click Next/Prev and verify page navigation.
3. Use Zoom + / Zoom - and verify render quality.
4. Rotate a page, then save and reopen to verify persistence.
5. Search for a word known to exist in the document.
6. Add a text stamp and verify it appears.
7. Draw a signature and click Stamp Signature.
8. Save As and open the output PDF in another viewer to confirm edits.
9. Click Digital Sign (PFX), choose a .p12/.pfx file, enter password, and save signed output.

### Certificate-Based Digital Signing

The app supports cryptographic signing using a PKCS#12 certificate (.p12 or .pfx).

1. Open or edit a PDF.
2. Click Digital Sign (PFX).
3. Select your .p12/.pfx certificate file.
4. Enter certificate password.
5. Optionally choose a visible signature block and page number.
6. Choose output filename.

The app saves a signed PDF that can be validated by PDF viewers that support digital signature verification.

### Build a Windows .exe

Build on Windows (recommended) for best compatibility.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --name PDFReaderSigner src\pdf_reader_app.py
```

Output executable:

- dist\PDFReaderSigner\PDFReaderSigner.exe

Optional single-file build (slower startup, larger binary):

```powershell
pyinstaller --noconfirm --windowed --onefile --name PDFReaderSigner src\pdf_reader_app.py
```

## One-Click Windows Installer (No Python Needed For End Users)

This repository now includes:

- GitHub Actions workflow: `.github/workflows/windows-installer.yml`
- Inno Setup script: `installer/PDFReaderSigner.iss`

It produces:

- `PDFReaderSigner-Setup.exe` (installer)

### How to build the installer from GitHub

1. Push this project to GitHub on the `main` branch.
2. In GitHub, open the `Actions` tab.
3. Select `Build Windows Installer`.
4. Click `Run workflow`.
5. When complete, open the workflow run and download the artifact named `PDFReaderSigner-Windows`.
6. Inside the artifact, run `PDFReaderSigner-Setup.exe` on Windows.

### End-user install experience

1. Double-click `PDFReaderSigner-Setup.exe`.
2. Follow the install wizard.
3. Launch `PDFReaderSigner` from Start menu or desktop shortcut.
4. Click `Open PDF` to open a document.

### Optional next hardening

- Code-sign the installer and app executable to reduce SmartScreen prompts.
