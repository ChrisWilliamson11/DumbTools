# Tooltip: Test the connection to Adobe Photoshop via COM interface for automation scripts
from photoshop import PhotoshopConnection

with PhotoshopConnection(password='photoshop') as conn:
    # Test layer operations
    print("Testing layer operations...")
    
    # Execute our layer manipulation script
    conn.execute('''
        var doc = app.activeDocument;
        var layer = doc.activeLayer;
        
        // Load the layer's transparency channel as a selection
        function SelectTransparency() {
            var idChnl = charIDToTypeID("Chnl");
            
            var actionSelect = new ActionReference();
            actionSelect.putProperty(idChnl, charIDToTypeID("fsel"));
            
            var actionTransparent = new ActionReference();
            actionTransparent.putEnumerated(idChnl, idChnl, charIDToTypeID("Trsp"));
            
            var actionDesc = new ActionDescriptor();
            actionDesc.putReference(charIDToTypeID("null"), actionSelect);
            actionDesc.putReference(charIDToTypeID("T   "), actionTransparent);
            
            executeAction(charIDToTypeID("setd"), actionDesc, DialogModes.NO);
        }
        
        // Select transparency
        SelectTransparency();
        
        // Fill with black
        var black = new SolidColor();
        black.rgb.red = 0;
        black.rgb.green = 0;
        black.rgb.blue = 0;

        doc.selection.fill(black, ColorBlendMode.NORMAL, 100, false);
        
        // Copy to clipboard
        layer.copy();
        
        // Clean up
        doc.selection.deselect();
    ''')