import Toybox.WatchUi;
import Toybox.System;
import Toybox.Attention;
import Toybox.Lang;

class GroceryDelegate extends WatchUi.BehaviorDelegate {
    private var _view as GroceryView;
    private var _service as GroceryService;

    function initialize(view as GroceryView, service as GroceryService) {
        BehaviorDelegate.initialize();
        _view = view;
        _service = service;
    }

    // Touch screen tap on an item (or tap to retry when empty)
    function onTap(clickEvent as WatchUi.ClickEvent) as Boolean {
        if (_view.rows.size() == 0) {
            _view.isLoading = true;
            WatchUi.requestUpdate();
            _service.fetchItems();
            return true;
        }

        var coords = clickEvent.getCoordinates();
        var clickedItem = _view.getItemAtCoordinates(coords[1]);

        if (clickedItem != null) {
            toggleItemState(clickedItem);
            return true;
        }
        return false;
    }

    // Touch screen swipe
    function onSwipe(swipeEvent as WatchUi.SwipeEvent) as Boolean {
        var direction = swipeEvent.getDirection();
        if (direction == WatchUi.SWIPE_UP) {
            _view.scrollDown();
            return true;
        } else if (direction == WatchUi.SWIPE_DOWN) {
            _view.scrollUp();
            return true;
        }
        return false;
    }

    // Physical Buttons: START / ENTER to toggle selected item
    function onSelect() as Boolean {
        var selected = _view.getSelectedItem();
        if (selected != null) {
            toggleItemState(selected);
            return true;
        }
        return false;
    }

    // Physical Buttons: UP / DOWN to navigate
    function onNextPage() as Boolean {
        _view.scrollDown();
        return true;
    }

    function onPreviousPage() as Boolean {
        _view.scrollUp();
        return true;
    }

    // Key event fallback
    function onKey(keyEvent as WatchUi.KeyEvent) as Boolean {
        var key = keyEvent.getKey();
        if (key == WatchUi.KEY_ENTER || key == WatchUi.KEY_START) {
            return onSelect();
        } else if (key == WatchUi.KEY_DOWN) {
            _view.scrollDown();
            return true;
        } else if (key == WatchUi.KEY_UP) {
            _view.scrollUp();
            return true;
        } else if (key == WatchUi.KEY_MENU) {
            // Long press MENU to force sync from server
            _view.isLoading = true;
            WatchUi.requestUpdate();
            _service.fetchItems();
            return true;
        }
        return false;
    }

    // Common toggle handler with haptic feedback
    private function toggleItemState(item as GroceryItem) as Void {
        item.toggleChecked();
        _service.toggleItem(item);

        // Gentle haptic confirmation
        if (Attention has :vibrate) {
            var vibeProfile = [ new Attention.VibeProfile(50, 100) ];
            Attention.vibrate(vibeProfile);
        }

        _view.onItemToggled(item);
    }
}
