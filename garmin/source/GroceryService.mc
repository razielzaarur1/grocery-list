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

    // Fetch items list from backend API
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
            var itemsList = [] as Array<GroceryItem>;
            var categories = data.get("categories") as Array<Dictionary>?;

            if (categories != null) {
                for (var c = 0; c < categories.size(); c++) {
                    var cat = categories[c];
                    var items = cat.get("items") as Array<Dictionary>?;
                    if (items != null) {
                        for (var i = 0; i < items.size(); i++) {
                            itemsList.add(new GroceryItem(items[i]));
                        }
                    }
                }
            }

            System.println("Parsed items count: " + itemsList.size());
            // Save to persistent storage for offline access
            saveOfflineItems(itemsList);
            _callback.invoke(true, itemsList, null);
        } else {
            // Offline fallback: load cached items from storage
            var cached = loadOfflineItems();
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
    private function saveOfflineItems(items as Array<GroceryItem>) as Void {
        try {
            var serialized = [] as Array<Dictionary>;
            for (var i = 0; i < items.size(); i++) {
                var it = items[i];
                serialized.add({
                    "id" => it.id,
                    "name" => it.name,
                    "quantity" => it.quantity,
                    "unit" => it.unit,
                    "note" => it.note,
                    "is_checked" => it.isChecked,
                    "category_id" => it.categoryId
                });
            }
            Application.Storage.setValue("cached_items", serialized);
        } catch (ex) {
            System.println("Failed to cache items: " + ex.getErrorMessage());
        }
    }

    function loadOfflineItems() as Array<GroceryItem> {
        var itemsList = [] as Array<GroceryItem>;
        try {
            var cached = Application.Storage.getValue("cached_items") as Array<Dictionary>?;
            if (cached != null) {
                for (var i = 0; i < cached.size(); i++) {
                    itemsList.add(new GroceryItem(cached[i]));
                }
            }
        } catch (ex) {
            System.println("Failed to load cached items: " + ex.getErrorMessage());
        }
        return itemsList;
    }
}
