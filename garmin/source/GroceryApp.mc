import Toybox.Application;
import Toybox.WatchUi;
import Toybox.Lang;

class GroceryApp extends Application.AppBase {
    private var _view as GroceryView?;
    private var _service as GroceryService?;

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state as Dictionary?) as Void {
    }

    function onStop(state as Dictionary?) as Void {
    }

    function getInitialView() as [Views] or [Views, InputDelegates] {
        _view = new GroceryView();
        _service = new GroceryService(method(:onItemsLoaded));

        // Immediately show cached items from storage for 0ms startup delay
        var cached = _service.loadOfflineItems();
        if (cached.size() > 0) {
            _view.setItems(cached, null);
        }

        // Fetch fresh list from server
        _service.fetchItems();

        var delegate = new GroceryDelegate(_view, _service);
        return [ _view, delegate ];
    }

    function onItemsLoaded(success as Boolean, items as Array<GroceryItem>, errorMsg as String?) as Void {
        if (_view != null) {
            _view.setItems(items, errorMsg);
        }
    }
}
