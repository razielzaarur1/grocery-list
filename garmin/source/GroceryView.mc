import Toybox.WatchUi;
import Toybox.Graphics;
import Toybox.System;
import Toybox.Lang;

class GroceryView extends WatchUi.View {
    var items as Array<GroceryItem> = [] as Array<GroceryItem>;
    var selectedIndex as Number = 0;
    var topIndex as Number = 0;
    var visibleCount as Number = 5; // 4 to 6 items per screen view (optimal: 5)
    var isLoading as Boolean = true;
    var statusMessage as String? = null;

    private var _rowHeight as Number = 64;
    private var _headerHeight as Number = 65;
    private var _screenWidth as Number = 454;
    private var _screenHeight as Number = 454;

    function initialize() {
        View.initialize();
    }

    function onLayout(dc as Graphics.Dc) as Void {
        _screenWidth = dc.getWidth();
        _screenHeight = dc.getHeight();
        _headerHeight = (_screenHeight * 0.15).toNumber();
        var availableHeight = _screenHeight - _headerHeight - 20;
        _rowHeight = (availableHeight / visibleCount).toNumber();
    }

    function onUpdate(dc as Graphics.Dc) as Void {
        // Pure AMOLED Black Background
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();

        // 1. Draw Top Header
        drawHeader(dc);

        // Loading or Empty or Error state
        if (isLoading) {
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                _screenWidth / 2,
                _screenHeight / 2,
                Graphics.FONT_SMALL,
                BidiHelper.shapeHebrew("טוען נתונים..."),
                Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
            );
            return;
        }

        if (items.size() == 0) {
            dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                _screenWidth / 2,
                _screenHeight / 2,
                Graphics.FONT_SMALL,
                BidiHelper.shapeHebrew("הרשימה ריקה"),
                Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
            );
            return;
        }

        // 2. Draw Items (4-6 items on screen)
        var endIndex = topIndex + visibleCount;
        if (endIndex > items.size()) {
            endIndex = items.size();
        }

        var startX = (_screenWidth * 0.12).toNumber();
        var itemWidth = (_screenWidth * 0.76).toNumber();

        for (var i = topIndex; i < endIndex; i++) {
            var item = items[i];
            var rowY = _headerHeight + ((i - topIndex) * _rowHeight);
            var isFocused = (i == selectedIndex);

            drawItemRow(dc, item, startX, rowY, itemWidth, _rowHeight, isFocused);
        }

        // 3. Draw Scroll Progress Indicator (Right Edge)
        drawScrollIndicator(dc);
    }

    private function drawHeader(dc as Graphics.Dc) as Void {
        var remaining = 0;
        for (var i = 0; i < items.size(); i++) {
            if (!items[i].isChecked) {
                remaining++;
            }
        }

        // Title
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        var titleText = BidiHelper.shapeHebrew("רשימת קניות");
        dc.drawText(
            _screenWidth / 2,
            18,
            Graphics.FONT_XTINY,
            titleText,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Subtitle (Remaining count)
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        var subText = BidiHelper.shapeHebrew(remaining + " נותרו מתוך " + items.size());
        dc.drawText(
            _screenWidth / 2,
            38,
            Graphics.FONT_SYSTEM_XTINY,
            subText,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Subtle separator line
        dc.setColor(0x334155, Graphics.COLOR_TRANSPARENT);
        dc.drawLine((_screenWidth * 0.2).toNumber(), _headerHeight - 6, (_screenWidth * 0.8).toNumber(), _headerHeight - 6);
    }

    private function drawItemRow(
        dc as Graphics.Dc,
        item as GroceryItem,
        x as Number,
        y as Number,
        width as Number,
        height as Number,
        isFocused as Boolean
    ) as Void {
        // Selection highlight box (for physical button focus)
        if (isFocused) {
            dc.setColor(0x1e293b, Graphics.COLOR_TRANSPARENT);
            dc.fillRoundedRectangle(x - 6, y, width + 12, height - 4, 8);
            dc.setColor(0x38bdf8, Graphics.COLOR_TRANSPARENT);
            dc.drawRoundedRectangle(x - 6, y, width + 12, height - 4, 8);
        }

        var textCenterY = y + (height / 2);
        var hasDetails = (item.shapedDetails.length() > 0);

        // Colors
        var textColor = item.isChecked ? Graphics.COLOR_DK_GRAY : Graphics.COLOR_WHITE;
        var subColor = item.isChecked ? Graphics.COLOR_DK_GRAY : 0x94a3b8;

        // Draw Text (Center Justified for curved AMOLED display)
        var nameY = hasDetails ? (y + 4) : (textCenterY - 10);
        dc.setColor(textColor, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            _screenWidth / 2,
            nameY,
            Graphics.FONT_SMALL,
            item.shapedName,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Draw Subtext (Quantity / Unit / Note)
        if (hasDetails) {
            dc.setColor(subColor, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                _screenWidth / 2,
                nameY + 24,
                Graphics.FONT_SYSTEM_XTINY,
                item.shapedDetails,
                Graphics.TEXT_JUSTIFY_CENTER
            );
        }

        // Strikethrough Line (קו מעל/חוצה - ללא צ'קבוקס!)
        if (item.isChecked) {
            dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
            // Draw clean strikethrough line across the item name
            var strikeY = nameY + 12;
            var textWidth = (item.name.length() * 14); // approximate width
            if (textWidth > width - 20) {
                textWidth = width - 20;
            }
            var lineStartX = (_screenWidth / 2) - (textWidth / 2);
            var lineEndX = lineStartX + textWidth;

            dc.setPenWidth(2);
            dc.drawLine(lineStartX, strikeY, lineEndX, strikeY);
            dc.setPenWidth(1);
        }
    }

    private function drawScrollIndicator(dc as Graphics.Dc) as Void {
        if (items.size() <= visibleCount) {
            return;
        }

        var indicatorHeight = 40;
        var trackHeight = _screenHeight * 0.5;
        var trackY = _screenHeight * 0.25;
        var progress = topIndex.toFloat() / (items.size() - visibleCount).toFloat();
        var indicatorY = trackY + (progress * (trackHeight - indicatorHeight)).toNumber();

        dc.setColor(0x475569, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(_screenWidth - 12, indicatorY, 4, indicatorHeight, 2);
    }

    // Navigation and Scrolling
    function scrollDown() as Void {
        if (selectedIndex < items.size() - 1) {
            selectedIndex++;
            if (selectedIndex >= topIndex + visibleCount) {
                topIndex = selectedIndex - visibleCount + 1;
            }
            WatchUi.requestUpdate();
        }
    }

    function scrollUp() as Void {
        if (selectedIndex > 0) {
            selectedIndex--;
            if (selectedIndex < topIndex) {
                topIndex = selectedIndex;
            }
            WatchUi.requestUpdate();
        }
    }

    function getSelectedItem() as GroceryItem? {
        if (items.size() > 0 && selectedIndex >= 0 && selectedIndex < items.size()) {
            return items[selectedIndex];
        }
        return null;
    }

    function getItemAtCoordinates(touchY as Number) as GroceryItem? {
        if (touchY < _headerHeight || touchY > _screenHeight - 15) {
            return null;
        }

        var clickedRelativeY = touchY - _headerHeight;
        var clickedSlot = (clickedRelativeY / _rowHeight).toNumber();
        var itemIndex = topIndex + clickedSlot;

        if (itemIndex >= 0 && itemIndex < items.size()) {
            selectedIndex = itemIndex;
            return items[itemIndex];
        }
        return null;
    }

    function setItems(newItems as Array<GroceryItem>, msg as String?) as Void {
        items = newItems;
        isLoading = false;
        statusMessage = msg;
        if (selectedIndex >= items.size()) {
            selectedIndex = items.size() > 0 ? items.size() - 1 : 0;
        }
        WatchUi.requestUpdate();
    }
}
