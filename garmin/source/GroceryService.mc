import Toybox.Communications;
import Toybox.Application;
import Toybox.Lang;
import Toybox.System;

class GroceryService {
    private var _callback as Method;
    private var _lastVersion as Number = -1;
    private var _isBusy as Boolean = false;
    private var _isOffline as Boolean = false;
    private var _pendingToggles as Array<Dictionary> = [] as Array<Dictionary>;
    private var _lastCategories as Array<GroceryCategoryData> = [] as Array<GroceryCategoryData>;

    function initialize(callback as Method) {
        _callback = callback;
        loadPendingToggles();
    }

    function isBusy() as Boolean {
        return _isBusy || (_pendingToggles.size() > 0);
    }

    function hasPendingToggles() as Boolean {
        return _pendingToggles.size() > 0;
    }

    function isOffline() as Boolean {
        return _isOffline;
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

    // Force full bidirectional sync (e.g. on manual refresh or MENU press)
    function forceSync() as Void {
        _lastVersion = -1;
        if (_pendingToggles.size() > 0) {
            processQueue();
        } else {
            fetchItems();
        }
    }

    // Check lightweight 15-byte version for real-time live sync
    function checkVersion() as Void {
        if (_isBusy) {
            return;
        }

        // If user made offline toggles while disconnected, prioritize flushing them to server first!
        if (_pendingToggles.size() > 0) {
            processQueue();
            return;
        }

        _isBusy = true;
        var url = getBaseUrl() + "/api/items/version";
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :headers => getHeaders(),
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };

        Communications.makeWebRequest(url, null, options, method(:onReceiveVersion));
    }

    function onReceiveVersion(responseCode as Number, data as Dictionary?) as Void {
        _isBusy = false;

        // If toggles were queued while checkVersion was in flight, execute them immediately!
        if (_pendingToggles.size() > 0) {
            processQueue();
            return;
        }

        if (responseCode == 200 && data != null) {
            _isOffline = false;
            var v = data.get("version");
            if (v != null) {
                var verNum = (v has :toNumber) ? v.toNumber() : 0;
                if (_lastVersion == -1 || verNum != _lastVersion) {
                    fetchItems();
                }
            }
        } else {
            _isOffline = true;
        }
    }

    // Fetch items grouped by category from backend API
    function fetchItems() as Void {
        if (_isBusy) {
            return;
        }

        if (_pendingToggles.size() > 0) {
            processQueue();
            return;
        }

        _isBusy = true;
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
        _isBusy = false;
        System.println("onReceiveItems code: " + responseCode);
        if (responseCode == 200 && data != null) {
            _isOffline = false;
            var v = data.get("version");
            if (v != null) {
                _lastVersion = (v has :toNumber) ? v.toNumber() : 0;
            }

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
            _lastCategories = categoriesList;
            saveOfflineCategories(categoriesList);
            _callback.invoke(true, categoriesList, null);
        } else {
            _isOffline = true;
            var cached = loadOfflineCategories();
            _lastCategories = cached;
            _callback.invoke(false, cached, "שגיאת חיבור (" + responseCode + ")");
        }

        // Process any queued user actions
        processQueue();
    }

    // Toggle item checked state: queues request to ensure 100% reliable BLE transmission & offline persistence
    function toggleItem(item as GroceryItem) as Void {
        var found = false;
        for (var i = 0; i < _pendingToggles.size(); i++) {
            if (_pendingToggles[i].get("id") == item.id) {
                _pendingToggles[i].put("isChecked", item.isChecked);
                found = true;
                break;
            }
        }
        if (!found) {
            _pendingToggles.add({
                "id" => item.id,
                "isChecked" => item.isChecked
            });
        }
        savePendingToggles();

        // Update local offline cache immediately so it stays in flash storage
        if (_lastCategories.size() > 0) {
            saveOfflineCategories(_lastCategories);
        }

        processQueue();
    }

    private function processQueue() as Void {
        if (_isBusy || _pendingToggles.size() == 0) {
            return;
        }

        _isBusy = true;
        var nextReq = _pendingToggles[0];
        var itemId = nextReq.get("id");
        var isChecked = nextReq.get("isChecked") as Boolean;

        var url = getBaseUrl() + "/api/items/" + itemId + "/toggle";
        // Non-null Dictionary for JSON POST is required by Garmin Connect Mobile
        var params = {
            "is_checked" => isChecked
        };
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_POST,
            :headers => getHeaders(),
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };

        Communications.makeWebRequest(url, params, options, method(:onToggleResponse));
    }

    function onToggleResponse(responseCode as Number, data as Dictionary?) as Void {
        _isBusy = false;
        System.println("Item toggle response: " + responseCode);

        if (_pendingToggles.size() == 0) {
            return;
        }

        if (responseCode == 200) {
            _isOffline = false;
            // Successfully delivered to server! Remove from queue and save updated queue
            _pendingToggles.remove(_pendingToggles[0]);
            savePendingToggles();

            // Update version so subsequent checkVersion won't trigger redundant fetch
            if (data != null && data.get("version") != null) {
                var v = data.get("version");
                _lastVersion = (v has :toNumber) ? v.toNumber() : _lastVersion;
            }

            if (_pendingToggles.size() > 0) {
                processQueue();
            } else {
                // All pending offline toggles have been successfully delivered to server!
                // Trigger version check now to confirm total harmony with server
                checkVersion();
            }
        } else {
            // Network failure / offline: responseCode < 0 (BLE disconnected / timeout) or 5xx
            // Keep item in persistent offline queue. DO NOT revert the item!
            // When internet or Bluetooth reconnects, the periodic timer will flush the queue.
            _isOffline = true;
            System.println("Toggle failed, retained in offline queue: " + responseCode);
        }
    }

    // Persistent storage caching for offline supermarket use
    private function savePendingToggles() as Void {
        try {
            var serialized = [] as Array<Dictionary>;
            for (var i = 0; i < _pendingToggles.size(); i++) {
                var t = _pendingToggles[i];
                serialized.add({
                    "id" => t.get("id"),
                    "isChecked" => t.get("isChecked")
                });
            }
            Application.Storage.setValue("pending_toggles", serialized);
        } catch (ex) {
            System.println("Failed to save pending toggles: " + ex.getErrorMessage());
        }
    }

    private function loadPendingToggles() as Void {
        try {
            var saved = Application.Storage.getValue("pending_toggles") as Array<Dictionary>?;
            if (saved != null && saved.size() > 0) {
                _pendingToggles = [] as Array<Dictionary>;
                for (var i = 0; i < saved.size(); i++) {
                    var itemDict = saved[i];
                    _pendingToggles.add({
                        "id" => itemDict.get("id"),
                        "isChecked" => itemDict.get("isChecked")
                    });
                }
            }
        } catch (ex) {
            System.println("Failed to load pending toggles: " + ex.getErrorMessage());
        }
    }

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
        _lastCategories = result;
        return result;
    }
}
