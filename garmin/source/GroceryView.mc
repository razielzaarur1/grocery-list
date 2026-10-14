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
    private var _font as Object? = null;
    private var _fontSmall as Object? = null;

    function initialize() {
        View.initialize();
    }

    function onLayout(dc as Graphics.Dc) as Void {
        _screenWidth = dc.getWidth();
        _screenHeight = dc.getHeight();
        _headerHeight = (_screenHeight * 0.15).toNumber();
        var availableHeight = _screenHeight - _headerHeight - 20;
        _rowHeight = (availableHeight / visibleCount).toNumber();

        try {
            _font = WatchUi.loadResource(Rez.Fonts.HebrewFont);
            _fontSmall = WatchUi.loadResource(Rez.Fonts.HebrewSmall);
        } catch (ex) {
            _font = null;
            _fontSmall = null;
        }
    }

    private function getMainFont() {
        return _font != null ? _font : Graphics.FONT_SMALL;
    }

    private function getSmallFont() {
        return _fontSmall != null ? _fontSmall : Graphics.FONT_SYSTEM_XTINY;
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
                getMainFont(),
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
                getMainFont(),
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
            14,
            getMainFont(),
            titleText,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Subtitle (Remaining count)
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        var subText = BidiHelper.shapeHebrew(remaining + " נותרו מתוך " + items.size());
        dc.drawText(
            _screenWidth / 2,
            40,
            getSmallFont(),
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

        var rightMargin = x + width - 6;
        var leftMargin = x + 6;

        var hasNote = (item.shapedNote.length() > 0);
        var hasQuantity = (item.shapedQuantity.length() > 0);

        var nameY = hasNote ? (y + 4) : (y + (height / 2) - 12);

        // Colors matching the web app:
        // Name: white (or dark gray when checked)
        // Quantity & Note: small grayish (0x94a3b8)
        var nameColor = item.isChecked ? Graphics.COLOR_DK_GRAY : Graphics.COLOR_WHITE;
        var grayColor = item.isChecked ? Graphics.COLOR_DK_GRAY : 0x94a3b8;

        // 1. Draw Item Name on the RIGHT (RTL)
        dc.setColor(nameColor, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            rightMargin,
            nameY,
            getMainFont(),
            item.shapedName,
            Graphics.TEXT_JUSTIFY_RIGHT
        );

        // 2. Draw Quantity on the LEFT (in small grayish, like web app)
        if (hasQuantity) {
            dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                leftMargin,
                nameY + 2,
                getSmallFont(),
                item.shapedQuantity,
                Graphics.TEXT_JUSTIFY_LEFT
            );
        }

        // 3. Draw Note directly UNDERNEATH the item name (in small grayish, like web app)
        if (hasNote) {
            dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                rightMargin,
                nameY + 24,
                getSmallFont(),
                item.shapedNote,
                Graphics.TEXT_JUSTIFY_RIGHT
            );
        }

        // 4. Strikethrough Line (קו חוצה מעל הטקסט - ללא צ'קבוקס!)
        if (item.isChecked) {
            dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth(2);

            // Strikethrough over name
            var nameLen = (item.name.length() * 12);
            if (nameLen > (width * 0.65).toNumber()) {
                nameLen = (width * 0.65).toNumber();
            }
            dc.drawLine(rightMargin, nameY + 11, rightMargin - nameLen, nameY + 11);

            // Strikethrough over note if present
            if (hasNote) {
                var noteLen = (item.note.length() * 9);
                if (noteLen > (width * 0.65).toNumber()) {
                    noteLen = (width * 0.65).toNumber();
                }
                dc.drawLine(rightMargin, nameY + 31, rightMargin - noteLen, nameY + 31);
            }

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
