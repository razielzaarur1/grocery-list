import Toybox.Lang;

class GroceryItem {
    var id as Number;
    var name as String;
    var quantity as String;
    var unit as String;
    var note as String;
    var isChecked as Boolean;
    var categoryId as Number;

    // Pre-calculated shaped text for fast drawing
    var shapedName as String;
    var shapedDetails as String;

    function initialize(dict as Dictionary) {
        id = dict.get("id") as Number;
        name = dict.get("name") != null ? dict.get("name").toString() : "";
        quantity = dict.get("quantity") != null ? dict.get("quantity").toString() : "";
        unit = dict.get("unit") != null ? dict.get("unit").toString() : "";
        note = dict.get("note") != null ? dict.get("note").toString() : "";
        isChecked = dict.get("is_checked") != null ? dict.get("is_checked") as Boolean : false;
        categoryId = dict.get("category_id") != null ? dict.get("category_id") as Number : 0;

        updateShapedText();
    }

    function updateShapedText() as Void {
        shapedName = BidiHelper.shapeHebrew(name);

        var details = "";
        if (quantity.length() > 0) {
            details += quantity;
            if (unit.length() > 0) {
                details += " " + unit;
            }
        } else if (unit.length() > 0) {
            details += unit;
        }

        if (note.length() > 0) {
            if (details.length() > 0) {
                details += " • " + note;
            } else {
                details += note;
            }
        }

        shapedDetails = BidiHelper.shapeHebrew(details);
    }

    function toggleChecked() as Void {
        isChecked = !isChecked;
    }
}
