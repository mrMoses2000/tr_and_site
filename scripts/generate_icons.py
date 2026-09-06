import os
import pymupdf
from PIL import Image

# SVG design for Logos Bible Institute Emblem
SVG_EMBLEM = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <!-- Background Gradient: Deep Academic Burgundy / Oxblood -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#4e0d10"/>
      <stop offset="45%" stop-color="#7a181d"/>
      <stop offset="100%" stop-color="#2d0608"/>
    </linearGradient>

    <!-- Gold Foil Gradients -->
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#faecc8"/>
      <stop offset="35%" stop-color="#d4af37"/>
      <stop offset="70%" stop-color="#aa8222"/>
      <stop offset="100%" stop-color="#f5e2b3"/>
    </linearGradient>

    <linearGradient id="goldLight" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#fff8e7"/>
      <stop offset="50%" stop-color="#dfbe6f"/>
      <stop offset="100%" stop-color="#9d741e"/>
    </linearGradient>

    <linearGradient id="pageGradLeft" x1="100%" y1="0%" x2="0%" y2="0%">
      <stop offset="0%" stop-color="#ede3d1"/>
      <stop offset="15%" stop-color="#f9f5ec"/>
      <stop offset="100%" stop-color="#ffffff"/>
    </linearGradient>

    <linearGradient id="pageGradRight" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#ede3d1"/>
      <stop offset="15%" stop-color="#f9f5ec"/>
      <stop offset="100%" stop-color="#ffffff"/>
    </linearGradient>

    <linearGradient id="ribbonGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#8a171c"/>
      <stop offset="50%" stop-color="#b8272e"/>
      <stop offset="100%" stop-color="#690e12"/>
    </linearGradient>

    <filter id="shadow" x="-15%" y="-15%" width="130%" height="130%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000000" flood-opacity="0.5"/>
    </filter>

    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Base Rounded Squircle with Gold Border -->
  <rect x="8" y="8" width="496" height="496" rx="116" fill="url(#bgGrad)"/>
  <rect x="12" y="12" width="488" height="488" rx="112" fill="none" stroke="url(#goldGrad)" stroke-width="7" opacity="0.9"/>
  <rect x="24" y="24" width="464" height="464" rx="100" fill="none" stroke="url(#goldGrad)" stroke-width="1.5" opacity="0.4" stroke-dasharray="8 6"/>

  <!-- Subtle Radial Divine Light behind the Book & Lambda -->
  <radialGradient id="divineLight" cx="50%" cy="45%" r="40%">
    <stop offset="0%" stop-color="#faecc8" stop-opacity="0.28"/>
    <stop offset="50%" stop-color="#d4af37" stop-opacity="0.1"/>
    <stop offset="100%" stop-color="#4e0d10" stop-opacity="0"/>
  </radialGradient>
  <circle cx="256" cy="240" r="190" fill="url(#divineLight)"/>

  <!-- Radiating Star / Light at Apex -->
  <g transform="translate(256, 92)" filter="url(#glow)">
    <!-- 8-pointed star of divine wisdom -->
    <path d="M0,-24 L4,-7 L21,-21 L7,-4 L24,0 L7,4 L21,21 L4,7 L0,24 L-4,7 L-21,21 L-7,4 L-24,0 L-7,-4 L-21,-21 L-4,-7 Z" fill="url(#goldLight)"/>
    <circle cx="0" cy="0" r="3.5" fill="#ffffff"/>
  </g>

  <!-- Gilded Book / Scripture Pages -->
  <g filter="url(#shadow)">
    <!-- Book Base / Cover Rim Underneath -->
    <path d="M72,352 Q164,374 256,358 Q348,374 440,352 L444,364 Q350,388 256,372 Q162,388 68,364 Z" fill="#9a7223"/>

    <!-- Left Open Page Folio (Curved Codex) -->
    <path d="M80,344 Q166,362 254,346 L254,232 Q166,246 80,228 Z" fill="url(#pageGradLeft)"/>
    <!-- Left Page Texture / Ruled Scholarly Lines -->
    <g opacity="0.32" stroke="#9a742c" stroke-width="2.2" stroke-linecap="round">
      <line x1="108" y1="256" x2="228" y2="267"/>
      <line x1="108" y1="274" x2="228" y2="285"/>
      <line x1="108" y1="292" x2="228" y2="303"/>
      <line x1="108" y1="310" x2="228" y2="321"/>
      <line x1="108" y1="328" x2="190" y2="337"/>
    </g>

    <!-- Right Open Page Folio (Curved Codex) -->
    <path d="M432,344 Q346,362 258,346 L258,232 Q346,246 432,228 Z" fill="url(#pageGradRight)"/>
    <!-- Right Page Texture / Ruled Scholarly Lines -->
    <g opacity="0.32" stroke="#9a742c" stroke-width="2.2" stroke-linecap="round">
      <line x1="284" y1="267" x2="404" y2="256"/>
      <line x1="284" y1="285" x2="404" y2="274"/>
      <line x1="284" y1="303" x2="404" y2="292"/>
      <line x1="284" y1="321" x2="404" y2="310"/>
      <line x1="284" y1="337" x2="366" y2="328"/>
    </g>

    <!-- Center Binding Ridge -->
    <path d="M253,230 L259,230 L259,350 L253,350 Z" fill="#b9933f"/>

    <!-- Bookmark Ribbon Cascading Down -->
    <path d="M246,346 L266,346 L268,432 L256,418 L244,432 Z" fill="url(#ribbonGrad)" stroke="url(#goldGrad)" stroke-width="1.5"/>
  </g>

  <!-- Classical Greek Letter LAMBDA (Λ) for ЛОГОС / LOGOS -->
  <!-- Classical serif typography rising heroically behind & uniting the scripture -->
  <g filter="url(#shadow)">
    <!-- Main Lambda Silhouette with Flared Classical Serifs -->
    <path d="M256,124 L276,124 L368,316 L384,320 L384,326 L324,326 L324,320 L340,316 L288,206 L224,316 L240,320 L240,326 L174,326 L174,320 L190,316 L256,124 Z"
          fill="url(#goldGrad)"
          stroke="#523908"
          stroke-width="2"/>

    <!-- Left Leg Highlight Contour -->
    <path d="M256,127 L200,314 L186,317 L226,317 L276,206 L264,136 Z"
          fill="url(#goldLight)"
          opacity="0.85"/>

    <!-- Serif Detailing on Top Apex -->
    <path d="M244,126 L278,126 L278,131 L244,131 Z" fill="#ffeec7"/>
  </g>

  <!-- Bottom Academic Typography Badge: LOGOS -->
  <g transform="translate(256, 466)">
    <text text-anchor="middle" font-family="'Cinzel', 'Trajan Pro', 'Georgia', serif" font-size="28" font-weight="700" letter-spacing="10" fill="url(#goldGrad)">ЛОГОС</text>
  </g>
</svg>"""

print("Writing favicon.svg and generating companion PNGs...")
os.makedirs("app/public", exist_ok=True)
with open("app/public/favicon.svg", "w", encoding="utf-8") as f:
    f.write(SVG_EMBLEM)

# Generate PNGs using pymupdf
doc = pymupdf.open("app/public/favicon.svg")
page = doc[0]
w0 = page.rect.width
h0 = page.rect.height

def render_size(target_w, target_h, filename):
    mat = pymupdf.Matrix(target_w / w0, target_h / h0)
    pix = page.get_pixmap(matrix=mat, alpha=True)
    pix.save(filename)
    print(f"Saved {filename} ({pix.width}x{pix.height})")

# 512x512
render_size(512, 512, "app/public/icon-512.png")

# 192x192
render_size(192, 192, "app/public/icon-192.png")

# 180x180 (Apple touch icon)
render_size(180, 180, "app/public/apple-touch-icon.png")

# 32x32 & 16x16
render_size(32, 32, "app/public/favicon-32x32.png")
render_size(16, 16, "app/public/favicon-16x16.png")

# Save ICO
img32 = Image.open("app/public/favicon-32x32.png")
img16 = Image.open("app/public/favicon-16x16.png")
img32.save("app/public/favicon.ico", format="ICO", sizes=[(32, 32), (16, 16)])
print("Saved app/public/favicon.ico")

print("Favicons and app icons generated successfully.")
