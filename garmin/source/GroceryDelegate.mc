import Toybox.WatchUi;
import Toybox.System;
import Toybox.Lang;

class GroceryDelegate extends WatchUi.BehaviorDelegate {
    private var _view as GroceryView;
    private var _service as GroceryService;

    function initialize(view as GroceryView, service as GroceryService) {
        BehaviorDelegate.initialize();
        _view = view;
        _service = service;
    }

    private var _lastDragY as Number? = null;
    private var _wasDragging as Boolean = false;

    // Smooth touch scrolling via onDrag
    function onDrag(dragEvent as WatchUi.DragEvent) as Boolean {
        var coords = dragEvent.getCoordinates();
        var y = coords[1];
        var dragType = dragEvent.getType();

        if (dragType == WatchUi.DRAG_TYPE_START) {
            _lastDragY = y;
            _wasDragging = false;
        } else if (dragType == WatchUi.DRAG_TYPE_CONTINUE) {
            if (_lastDragY != null) {
                var delta = y - _lastDragY;
                if (delta != 0) {
                    _wasDragging = true;
                    _view.scrollPixels(-delta);
                    _lastDragY = y;
                }
            } else {
                _lastDragY = y;
            }
        } else if (dragType == WatchUi.DRAG_TYPE_STOP) {
            _lastDragY = null;
        }
        return true;
    }

    // Touch screen tap on an item (or tap to retry when empty)
    function onTap(clickEvent as WatchUi.ClickEvent) as Boolean {
        if (_wasDragging) {
            _wasDragging = false;
            return true;
        }

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

    // Touch screen swipe: ignore when dragging was active to avoid violent jumps
    function onSwipe(swipeEvent as WatchUi.SwipeEvent) as Boolean {
        if (_wasDragging) {
            _wasDragging = false;
            return true;
        }
        var direction = swipeEvent.getDirection();
        if (direction == WatchUi.SWIPE_UP) {
            _view.scrollPixels(50);
            return true;
        } else if (direction == WatchUi.SWIPE_DOWN) {
            _view.scrollPixels(-50);
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

    // Common toggle handler (no vibration)
    private function toggleItemState(item as GroceryItem) as Void {
        item.toggleChecked();
        _service.toggleItem(item);
        _view.onItemToggled(item);
    }
}
