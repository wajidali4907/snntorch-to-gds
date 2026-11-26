# Render the metal layers of an ASAP7 GDS to a PNG.
#   klayout -zz -r scripts/render_gds.py -rd gds=<in.gds> -rd png=<out.png>
import pya
LAYERS = [(19, "M1", 0xb8c4d6), (20, "M2", 0x3b78c2), (30, "M3", 0x2e9e5b), (40, "M4", 0xe08a1e),
          (50, "M5", 0xd23b3b), (60, "M6", 0x8a4fc7), (70, "M7", 0x6b4a2b)]
lv = pya.LayoutView()
lv.load_layout(gds, False)
lv.clear_layers()
for num, name, col in reversed(LAYERS):      # first inserted is drawn on top
    p = pya.LayerProperties()
    p.source = f"{num}/0"
    p.name = name
    p.fill_color = p.frame_color = col
    p.dither_pattern = 0                     # solid
    p.width = 1
    lv.insert_layer(lv.end_layers(), p)
lv.max_hier()
for k, v in [("background-color", "#ffffff"), ("grid-visible", "false"), ("text-visible", "false")]:
    lv.set_config(k, v)
lv.zoom_fit()
lv.save_image(png, 2000, 2000)
print("wrote", png, lv.box())
