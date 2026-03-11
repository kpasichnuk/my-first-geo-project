import os
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageTk

try:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields
    from pyhanko.sign import signers

    HAS_PYHANKO = True
except ImportError:
    HAS_PYHANKO = False


class SignaturePad(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Draw Signature")
        self.geometry("600x260")
        self.resizable(False, False)

        self.signature_image = Image.new("RGBA", (560, 180), (255, 255, 255, 0))
        self.draw = ImageDraw.Draw(self.signature_image)
        self.last_x = None
        self.last_y = None
        self.result = None

        tk.Label(self, text="Draw your signature below", font=("Segoe UI", 11, "bold")).pack(pady=(10, 5))

        self.canvas = tk.Canvas(
            self,
            bg="white",
            width=560,
            height=180,
            highlightthickness=1,
            highlightbackground="#999",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw_signature)
        self.canvas.bind("<ButtonRelease-1>", self.stop_draw)

        button_frame = tk.Frame(self)
        button_frame.pack(pady=8)
        tk.Button(button_frame, text="Clear", command=self.clear).pack(side=tk.LEFT, padx=6)
        tk.Button(button_frame, text="Use Signature", command=self.accept).pack(side=tk.LEFT, padx=6)

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def start_draw(self, event):
        self.last_x, self.last_y = event.x, event.y

    def draw_signature(self, event):
        if self.last_x is None or self.last_y is None:
            return
        self.canvas.create_line(
            self.last_x,
            self.last_y,
            event.x,
            event.y,
            fill="black",
            width=2,
            capstyle=tk.ROUND,
            smooth=True,
        )
        self.draw.line((self.last_x, self.last_y, event.x, event.y), fill=(0, 0, 0, 255), width=2)
        self.last_x, self.last_y = event.x, event.y

    def stop_draw(self, _event):
        self.last_x, self.last_y = None, None

    def clear(self):
        self.canvas.delete("all")
        self.signature_image = Image.new("RGBA", (560, 180), (255, 255, 255, 0))
        self.draw = ImageDraw.Draw(self.signature_image)

    def accept(self):
        bbox = self.signature_image.getbbox()
        if not bbox:
            messagebox.showwarning("Empty Signature", "Please draw your signature first.")
            return
        self.result = self.signature_image.crop(bbox)
        self.close()

    def close(self):
        self.grab_release()
        self.destroy()


class PDFEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Reader/Writer + Signature")
        self.root.geometry("1050x760")

        self.doc = None
        self.pdf_path = None
        self.page_index = 0
        self.zoom = 1.2
        self.signature_img = None
        self.page_photo = None

        self._build_ui()

    def _build_ui(self):
        toolbar = tk.Frame(self.root, bd=1, relief=tk.FLAT, padx=6, pady=6)
        toolbar.pack(fill=tk.X)

        tk.Button(toolbar, text="Open PDF", command=self.open_pdf).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Save As", command=self.save_as).pack(side=tk.LEFT, padx=3)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Prev", command=self.prev_page).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Next", command=self.next_page).pack(side=tk.LEFT, padx=3)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Zoom +", command=self.zoom_in).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Zoom -", command=self.zoom_out).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Rotate Left", command=lambda: self.rotate_page(-90)).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Rotate Right", command=lambda: self.rotate_page(90)).pack(side=tk.LEFT, padx=3)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self.search_var, width=22).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Search", command=self.search_text).pack(side=tk.LEFT, padx=3)

        tk.Label(toolbar, text="|").pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Add Text Stamp", command=self.add_text_stamp).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Draw Signature", command=self.capture_signature).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Stamp Signature", command=self.stamp_signature).pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="Digital Sign (PFX)", command=self.digitally_sign_pdf).pack(side=tk.LEFT, padx=3)

        self.page_info = tk.Label(toolbar, text="No document loaded")
        self.page_info.pack(side=tk.RIGHT, padx=5)

        viewer_frame = tk.Frame(self.root)
        viewer_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(viewer_frame, bg="#2d2d2d")
        self.vbar = tk.Scrollbar(viewer_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.hbar = tk.Scrollbar(viewer_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)

        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def open_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        try:
            self.doc = fitz.open(path)
            self.pdf_path = path
            self.page_index = 0
            self.zoom = 1.2
            self.render_page()
        except (RuntimeError, ValueError, OSError) as exc:
            messagebox.showerror("Open Error", f"Failed to open PDF:\n{exc}")

    def render_page(self):
        if not self.doc:
            return

        page = self.doc[self.page_index]
        matrix = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.page_photo = ImageTk.PhotoImage(img)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.page_photo)
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.page_info.config(text=f"Page {self.page_index + 1}/{len(self.doc)} | Zoom {int(self.zoom * 100)}%")

    def prev_page(self):
        if not self.doc or self.page_index == 0:
            return
        self.page_index -= 1
        self.render_page()

    def next_page(self):
        if not self.doc or self.page_index >= len(self.doc) - 1:
            return
        self.page_index += 1
        self.render_page()

    def zoom_in(self):
        if not self.doc:
            return
        self.zoom = min(5.0, self.zoom + 0.2)
        self.render_page()

    def zoom_out(self):
        if not self.doc:
            return
        self.zoom = max(0.4, self.zoom - 0.2)
        self.render_page()

    def rotate_page(self, angle):
        if not self.doc:
            return
        page = self.doc[self.page_index]
        current = page.rotation
        page.set_rotation((current + angle) % 360)
        self.render_page()

    def search_text(self):
        if not self.doc:
            return
        term = self.search_var.get().strip()
        if not term:
            messagebox.showinfo("Search", "Enter text to search.")
            return

        for idx in range(len(self.doc)):
            if self.doc[idx].search_for(term):
                self.page_index = idx
                self.render_page()
                messagebox.showinfo("Search", f"Found '{term}' on page {idx + 1}.")
                return

        messagebox.showinfo("Search", f"'{term}' was not found in this document.")

    def add_text_stamp(self):
        if not self.doc:
            return
        text = simpledialog.askstring("Text Stamp", "Enter text to insert on current page:")
        if not text:
            return

        page = self.doc[self.page_index]
        page.insert_text((72, 72), text, fontsize=16, color=(0, 0, 0))
        self.render_page()

    def capture_signature(self):
        pad = SignaturePad(self.root)
        self.root.wait_window(pad)
        if pad.result is not None:
            self.signature_img = pad.result
            messagebox.showinfo("Signature", "Signature captured successfully.")

    def stamp_signature(self):
        if not self.doc:
            return
        if self.signature_img is None:
            messagebox.showwarning("No Signature", "Draw a signature first.")
            return

        page = self.doc[self.page_index]
        page_rect = page.rect

        target_w = page_rect.width * 0.28
        ratio = self.signature_img.height / max(1, self.signature_img.width)
        target_h = target_w * ratio

        margin = 24
        rect = fitz.Rect(
            page_rect.width - target_w - margin,
            page_rect.height - target_h - margin,
            page_rect.width - margin,
            page_rect.height - margin,
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self.signature_img.save(tmp_path, format="PNG")
            page.insert_image(rect, filename=tmp_path, keep_proportion=True, overlay=True)
            self.render_page()
            messagebox.showinfo("Signature", "Signature stamped on current page.")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def save_as(self):
        if not self.doc:
            return

        initial_name = "edited_" + (os.path.basename(self.pdf_path) if self.pdf_path else "document.pdf")
        out_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=initial_name,
            filetypes=[("PDF files", "*.pdf")],
        )
        if not out_path:
            return

        try:
            self.doc.save(out_path, garbage=4, deflate=True)
            messagebox.showinfo("Saved", f"Saved to:\n{out_path}")
        except (RuntimeError, ValueError, OSError) as exc:
            messagebox.showerror("Save Error", f"Failed to save PDF:\n{exc}")

    @staticmethod
    def _sign_with_pkcs12(input_pdf, output_pdf, cert_path, cert_password, page_number=None, total_pages=None):
        signer = signers.SimpleSigner.load_pkcs12(
            pfx_file=cert_path,
            passphrase=cert_password.encode("utf-8"),
        )
        if signer is None:
            raise ValueError("Could not load certificate. Check the file and password.")

        with open(input_pdf, "rb") as infile, open(output_pdf, "wb") as outfile:
            writer = IncrementalPdfFileWriter(infile)

            # Create a visible signature field if requested.
            if page_number is not None:
                if total_pages is None:
                    raise ValueError("Total page count is required for visible signatures.")
                if page_number < 1 or page_number > total_pages:
                    raise ValueError(f"Page number must be between 1 and {total_pages}.")

                field_name = f"Signature{page_number}"
                fields.append_signature_field(
                    writer,
                    sig_field_spec=fields.SigFieldSpec(
                        sig_field_name=field_name,
                        on_page=page_number - 1,
                        box=(360, 36, 560, 106),
                    ),
                )
            else:
                field_name = "Signature1"

            signature_meta = signers.PdfSignatureMetadata(field_name=field_name)
            pdf_signer = signers.PdfSigner(signature_meta=signature_meta, signer=signer)
            pdf_signer.sign_pdf(writer, output=outfile)

    def digitally_sign_pdf(self):
        if not self.doc:
            return
        if not HAS_PYHANKO:
            messagebox.showerror(
                "Missing Dependency",
                "pyHanko is not installed. Run: pip install pyhanko",
            )
            return

        cert_path = filedialog.askopenfilename(
            title="Select certificate",
            filetypes=[("PKCS#12 Certificate", "*.p12 *.pfx")],
        )
        if not cert_path:
            return

        cert_password = simpledialog.askstring(
            "Certificate Password",
            "Enter the password for your .p12/.pfx certificate:",
            show="*",
        )
        if cert_password is None:
            return

        visible_signature = messagebox.askyesno(
            "Visible Signature",
            "Do you want a visible signature block on the page?",
        )

        page_number = None
        if visible_signature:
            page_number = simpledialog.askinteger(
                "Signature Page",
                f"Enter page number for signature (1-{len(self.doc)}):",
                minvalue=1,
                maxvalue=len(self.doc),
            )
            if page_number is None:
                return

        suggested_name = "signed_" + (os.path.basename(self.pdf_path) if self.pdf_path else "document.pdf")
        out_path = filedialog.asksaveasfilename(
            title="Save signed PDF as",
            defaultextension=".pdf",
            initialfile=suggested_name,
            filetypes=[("PDF files", "*.pdf")],
        )
        if not out_path:
            return

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            temp_input_path = tmp_pdf.name

        try:
            # Save in-memory edits first, then apply cryptographic signature.
            self.doc.save(temp_input_path, garbage=4, deflate=True)
            self._sign_with_pkcs12(
                temp_input_path,
                out_path,
                cert_path,
                cert_password,
                page_number,
                len(self.doc),
            )

            self.doc.close()
            self.doc = fitz.open(out_path)
            self.pdf_path = out_path
            self.page_index = 0
            self.render_page()
            messagebox.showinfo("Digital Signature", f"Signed PDF saved to:\n{out_path}")
        except (RuntimeError, ValueError, OSError) as exc:
            messagebox.showerror("Signing Error", f"Failed to digitally sign PDF:\n{exc}")
        finally:
            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)


def launch_app():
    root = tk.Tk()
    _ = PDFEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_app()
