import Toybox.Lang;

class GroceryCategoryData {
    var id as Number = 0;
    var name as String = "";
    var totalCount as Number = 0;
    var remainingCount as Number = 0;
    var items as Array<GroceryItem> = [] as Array<GroceryItem>;

    function initialize(dict as Dictionary) {
        var rawId = dict.get("id");
        if (rawId != null) {
            id = (rawId has :toNumber) ? rawId.toNumber() : 0;
        }
        name = dict.get("name") != null ? dict.get("name").toString() : "";
        var rawTotal = dict.get("total_count");
        if (rawTotal != null) {
            totalCount = (rawTotal has :toNumber) ? rawTotal.toNumber() : 0;
        }
        var rawRem = dict.get("remaining_count");
        if (rawRem != null) {
            remainingCount = (rawRem has :toNumber) ? rawRem.toNumber() : 0;
        }

        var itemsArr = dict.get("items") as Array<Dictionary>?;
        if (itemsArr != null) {
            for (var i = 0; i < itemsArr.size(); i++) {
                var it = new GroceryItem(itemsArr[i]);
                it.categoryName = name;
                items.add(it);
            }
        }
    }
}
