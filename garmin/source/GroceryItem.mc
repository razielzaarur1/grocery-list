import Toybox.Lang;

class GroceryItem {
    var id as Number = 0;
    var name as String = "";
    var quantity as String = "";
    var unit as String = "";
    var note as String = "";
    var isChecked as Boolean = false;
    var categoryId as Number = 0;

    // Pre-calculated shaped text for fast drawing
    var shapedName as String = "";
    var shapedQuantity as String = "";
    var shapedNote as String = "";

    function initialize(dict as Dictionary) {
        var rawId = dict.get("id");
        if (rawId != null) {
            id = (rawId has :toNumber) ? rawId.toNumber() : 0;
        }
        name = dict.get("name") != null ? dict.get("name").toString() : "";
        quantity = dict.get("quantity") != null ? dict.get("quantity").toString() : "";
        unit = dict.get("unit") != null ? dict.get("unit").toString() : "";
        note = dict.get("note") != null ? dict.get("note").toString() : "";
        isChecked = dict.get("is_checked") != null ? dict.get("is_checked") as Boolean : false;
        var rawCatId = dict.get("category_id");
        if (rawCatId != null) {
            categoryId = (rawCatId has :toNumber) ? rawCatId.toNumber() : 0;
        }

        updateShapedText();
    }

    function updateShapedText() as Void {
        shapedName = BidiHelper.shapeHebrew(name);

        var q = "";
        if (quantity.length() > 0) {
            q += quantity;
            if (unit.length() > 0) {
                q += " " + unit;
            }
        } else if (unit.length() > 0) {
            q += unit;
        }
        shapedQuantity = BidiHelper.shapeHebrew(q);

        shapedNote = (note.length() > 0) ? BidiHelper.shapeHebrew(note) : "";
    }

    function toggleChecked() as Void {
        isChecked = !isChecked;
    }
}
