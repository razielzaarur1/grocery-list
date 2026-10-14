import Toybox.Lang;

class GroceryRow {
    var isHeader as Boolean = false;
    var categoryId as Number = 0;
    var headerTitle as String = "";
    var headerCount as String = "";
    var item as GroceryItem? = null;
    var rowHeight as Number = 54;
    var fittedTitle as String = "";

    function initializeAsHeader(catId as Number, title as String, countStr as String) {
        isHeader = true;
        categoryId = catId;
        headerTitle = BidiHelper.shapeHebrew(title);
        headerCount = countStr;
        fittedTitle = "";
        item = null;
        rowHeight = 42;
    }

    function initializeAsItem(groceryItem as GroceryItem) {
        isHeader = false;
        item = groceryItem;
        categoryId = groceryItem.categoryId;
        headerTitle = "";
        headerCount = "";
        fittedTitle = "";
        var hasNote = (groceryItem.note.length() > 0);
        rowHeight = hasNote ? 76 : 54;
    }
}
