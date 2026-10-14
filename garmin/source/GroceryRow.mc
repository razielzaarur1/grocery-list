import Toybox.Lang;

class GroceryRow {
    var isHeader as Boolean = false;
    var categoryId as Number = 0;
    var headerTitle as String = "";
    var headerCount as String = "";
    var item as GroceryItem? = null;

    function initializeAsHeader(catId as Number, title as String, countStr as String) {
        isHeader = true;
        categoryId = catId;
        headerTitle = BidiHelper.shapeHebrew(title);
        headerCount = countStr;
        item = null;
    }

    function initializeAsItem(groceryItem as GroceryItem) {
        isHeader = false;
        item = groceryItem;
        categoryId = groceryItem.categoryId;
        headerTitle = "";
        headerCount = "";
    }
}
