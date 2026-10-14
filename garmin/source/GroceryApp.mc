import Toybox.Application;
import Toybox.WatchUi;
import Toybox.Lang;
import Toybox.Timer;

class GroceryApp extends Application.AppBase {
    private var _view as GroceryView?;
    private var _service as GroceryService?;
    private var _syncTimer as Timer.Timer?;

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state as Dictionary?) as Void {
    }

    function onStop(state as Dictionary?) as Void {
        if (_syncTimer != null) {
            _syncTimer.stop();
            _syncTimer = null;
        }
    }

    function getInitialView() as [Views] or [Views, InputDelegates] {
        _view = new GroceryView();
        _service = new GroceryService(method(:onCategoriesLoaded));

        // Immediately show cached items from storage for 0ms startup delay
        var cached = _service.loadOfflineCategories();
        if (cached.size() > 0) {
            _view.setCategories(cached, null);
        }

        // Fetch fresh list from server
        _service.fetchItems();

        // Start background live sync timer (polls lightweight 15-byte version check every 2.5 seconds)
        _syncTimer = new Timer.Timer();
        _syncTimer.start(method(:onSyncTick), 2500, true);

        var delegate = new GroceryDelegate(_view, _service);
        return [ _view, delegate ];
    }

    function onSyncTick() as Void {
        if (_service != null && _view != null && !_view.isLoading) {
            _service.checkVersion();
        }
    }

    function onCategoriesLoaded(success as Boolean, categories as Array<GroceryCategoryData>, errorMsg as String?) as Void {
        if (_view != null) {
            _view.setCategories(categories, errorMsg);
        }
    }
}
