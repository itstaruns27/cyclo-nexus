"""Render a .pptx to per-slide PNGs via LibreOffice (PDF) + PyMuPDF.  python render.py deck.pptx outdir"""
import subprocess, sys, pathlib, fitz
deck, out = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
subprocess.run([r"C:\Program Files\LibreOffice\program\soffice.exe", "--headless", "--convert-to", "pdf", "--outdir", str(out), str(deck)], check=True, capture_output=True)
doc = fitz.open(out / (deck.stem + ".pdf"))
for i, page in enumerate(doc, 1):
    page.get_pixmap(dpi=int(sys.argv[3]) if len(sys.argv) > 3 else 60).save(out / f"slide{i}.png")
print(len(doc), "slides ->", out)
