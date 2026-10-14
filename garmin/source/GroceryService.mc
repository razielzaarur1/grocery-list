import Toybox.Communications;
import Toybox.Application;
import Toybox.Lang;
import Toybox.System;

class GroceryService {
    private var _callback as Method;

    function initialize(callback as Method) {
        _callback = callback;
    }

    private function getBaseUrl() as String {
        var url = Application.Properties.getValue("serverUrl");
        if (url == null || url.length() == 0) {
            url = "http://127.0.0.1:8000";
        }
        // Remove trailing slash if present
        if (url.substring(url.length() - 1, url.length()).equals("/")) {
            url = url.substring(0, url.length() - 1);
        }
        return url;
    }

    private function getHeaders() as Dictionary {
        var headers = {
            "Content-Type" => Communications.REQUEST_CONTENT_TYPE_JSON
        };
        var token = Application.Properties.getValue("deviceToken");
        if (token != null && token.length() > 0) {
            headers.put("X-Device-Token", token);
        }
        return headers;
    }

    // Fetch items grouped by category from backend API
    function fetchItems() as Void {
        var url = getBaseUrl() + "/api/items";
        System.println("Fetching from URL: " + url);
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :headers => getHeaders(),
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };

        Communications.makeWebRequest(url, null, options, method(:onReceiveItems));
    }

    function onReceiveItems(responseCode as Number, data as Dictionary?) as Void {
        System.println("onReceiveItems code: " + responseCode);
        if (responseCode == 200 && data != null) {
            var categoriesList = [] as Array<GroceryCategoryData>;
            var rawCategories = data.get("categories") as Array<Dictionary>?;

            if (rawCategories != null) {
                for (var c = 0; c < rawCategories.size(); c++) {
                    var catData = new GroceryCategoryData(rawCategories[c]);
                    if (catData.items.size() > 0) {
                        categoriesList.add(catData);
                    }
                }
            }

            System.println("Parsed categories count: " + categoriesList.size());
            saveOfflineCategories(categoriesList);
            _callback.invoke(true, categoriesList, null);
        } else {
            var cached = loadOfflineCategories();
            _callback.invoke(false, cached, "שגיאת חיבור (" + responseCode + ")");
        }
    }

    // Toggle item checked state
    function toggleItem(item as GroceryItem) as Void {
        var url = getBaseUrl() + "/api/items/" + item.id + "/toggle";
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_POST,
            :headers => getHeaders(),
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };

        Communications.makeWebRequest(url, null, options, method(:onToggleResponse));
    }

    function onToggleResponse(responseCode as Number, data as Dictionary?) as Void {
        System.println("Item toggle response: " + responseCode);
    }

    // Persistent storage caching for offline supermarket use
    private function saveOfflineCategories(categories as Array<GroceryCategoryData>) as Void {
        try {
            var serialized = [] as Array<Dictionary>;
            for (var c = 0; c < categories.size(); c++) {
                var cat = categories[c];
                var itemsArr = [] as Array<Dictionary>;
                for (var i = 0; i < cat.items.size(); i++) {
                    var it = cat.items[i];
                    itemsArr.add({
                        "id" => it.id,
                        "name" => it.name,
                        "quantity" => it.quantity,
                        "unit" => it.unit,
                        "note" => it.note,
                        "is_checked" => it.isChecked,
                        "category_id" => it.categoryId,
                        "global_add_order" => it.globalAddOrder
                    });
                }
                serialized.add({
                    "id" => cat.id,
                    "name" => cat.name,
                    "total_count" => cat.totalCount,
                    "remaining_count" => cat.remainingCount,
                    "items" => itemsArr
                });
            }
            Application.Storage.setValue("cached_categories", serialized);
        } catch (ex) {
            System.println("Failed to cache: " + ex.getErrorMessage());
        }
    }

    function loadOfflineCategories() as Array<GroceryCategoryData> {
        var result = [] as Array<GroceryCategoryData>;
        try {
            var cached = Application.Storage.getValue("cached_categories") as Array<Dictionary>?;
            if (cached != null) {
                for (var c = 0; c < cached.size(); c++) {
                    result.add(new GroceryCategoryData(cached[c]));
                }
            }
        } catch (ex) {
            System.println("Failed to load cached: " + ex.getErrorMessage());
        }
        return result;
    }
}
