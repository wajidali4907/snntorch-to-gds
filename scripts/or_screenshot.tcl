# OpenROAD GUI screenshots of a finished design, all at the same scale.
# openroad -no_init -gui -exit scripts/or_screenshot.tcl   (env: ODB, OUT)
read_db $::env(ODB)
set res 0.05 ;# microns per pixel, same for every design
gui::fit
gui::set_display_controls "*" visible false
gui::set_display_controls "Layers/*" visible true
gui::set_display_controls "Nets/*" visible true
gui::set_display_controls "Instances/*" visible true
gui::set_display_controls "Shape Types/*" visible true
gui::set_display_controls "Misc/Instances/*" visible false
gui::set_display_controls "Misc/Scale bar" visible true
gui::set_display_controls "Misc/Detailed view" visible true
save_image -resolution $res $::env(OUT)_all.png
gui::set_display_controls "Nets/Power" visible false
gui::set_display_controls "Nets/Ground" visible false
save_image -resolution $res $::env(OUT)_routing.png
gui::set_display_controls "Shape Types/Routing/*" visible false
gui::set_display_controls "Instances/Physical/*" visible false
save_image -resolution $res $::env(OUT)_placement.png
