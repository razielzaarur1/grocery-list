import Toybox.WatchUi;
import Toybox.Graphics;
import Toybox.System;
import Toybox.Lang;

class GroceryView extends WatchUi.View {
    var categories as Array<GroceryCategoryData> = [] as Array<GroceryCategoryData>;
    var rows as Array<GroceryRow> = [] as Array<GroceryRow>;
    var selectedIndex as Number = 0;
    var scrollY as Number = 0;
    var totalContentHeight as Number = 0;
    var isLoading as Boolean = true;
    var statusMessage as String? = null;

    private var _headerHeight as Number = 84;
    private var _screenWidth as Number = 454;
    private var _screenHeight as Number = 454;

    private var _cachedTitle as String = "רשימת קניות";
    private var _cachedRemSuffix as String = "נותרו";
    private var _cachedLoading as String = "טוען נתונים...";
    private var _cachedEmpty as String = "הרשימה ריקה";

    function initialize() {
        View.initialize();
    }

    function onLayout(dc as Graphics.Dc) as Void {
        _screenWidth = dc.getWidth();
        _screenHeight = dc.getHeight();
        _headerHeight = 84;

        try {
            _cachedTitle = WatchUi.loadResource(Rez.Strings.AppName) as String;
            _cachedRemSuffix = WatchUi.loadResource(Rez.Strings.RemainingSuffix) as String;
            _cachedLoading = WatchUi.loadResource(Rez.Strings.LoadingText) as String;
            _cachedEmpty = WatchUi.loadResource(Rez.Strings.EmptyText) as String;
        } catch (ex) {
        }
    }

    function getMainFont() {
        return Graphics.FONT_TINY;
    }

    function getSmallFont() {
        return Graphics.FONT_XTINY;
    }

    function getMaxScroll() as Number {
        var visibleArea = _screenHeight - _headerHeight - 16;
        var max = totalContentHeight - visibleArea;
        return max > 0 ? max : 0;
    }

    function scrollPixels(delta as Number) as Void {
        scrollY += delta;
        var max = getMaxScroll();
        if (scrollY > max) {
            scrollY = max;
        }
        if (scrollY < 0) {
            scrollY = 0;
        }
        WatchUi.requestUpdate();
    }

    private function truncateStringToWidth(
        dc as Graphics.Dc,
        text as String,
        font as Graphics.FontDefinition,
        maxWidth as Number
    ) as String {
        if (text == null || text.length() == 0) {
            return "";
        }
        var fullW = dc.getTextWidthInPixels(text, font);
        if (fullW <= maxWidth) {
            return text;
        }

        var ell = "..";
        var ellW = dc.getTextWidthInPixels(ell, font);
        var targetW = maxWidth - ellW;
        if (targetW <= 10) {
            return text;
        }

        var chars = text.toCharArray();
        var numChars = chars.size();
        var curStr = "";

        for (var i = 0; i < numChars; i++) {
            var nextStr = curStr + chars[i].toString();
            var nextW = dc.getTextWidthInPixels(nextStr, font);
            if (nextW > targetW) {
                return curStr + ell;
            }
            curStr = nextStr;
        }

        return curStr + ell;
    }

    // Rebuilds rows: category headers first, unchecked items, then checked items at the bottom of the category!
    function rebuildRows() as Void {
        rows = [] as Array<GroceryRow>;

        for (var c = 0; c < categories.size(); c++) {
            var cat = categories[c];
            if (cat.items.size() == 0) {
                continue;
            }

            var uncheckedList = [] as Array<GroceryItem>;
            var checkedList = [] as Array<GroceryItem>;

            for (var i = 0; i < cat.items.size(); i++) {
                var it = cat.items[i];
                if (it.isChecked) {
                    checkedList.add(it);
                } else {
                    uncheckedList.add(it);
                }
            }

            cat.remainingCount = uncheckedList.size();
            cat.totalCount = cat.items.size();

            // 1. Category Header Row
            var countStr = cat.remainingCount + "/" + cat.totalCount;
            var headerRow = new GroceryRow();
            headerRow.initializeAsHeader(cat.id, cat.name, countStr);
            rows.add(headerRow);

            // 2. Unchecked Items (appear right under header)
            for (var u = 0; u < uncheckedList.size(); u++) {
                var itemRow = new GroceryRow();
                itemRow.initializeAsItem(uncheckedList[u]);
                rows.add(itemRow);
            }

            // 3. Checked Items (placed at the bottom of the category!)
            for (var k = 0; k < checkedList.size(); k++) {
                var itemRow = new GroceryRow();
                itemRow.initializeAsItem(checkedList[k]);
                rows.add(itemRow);
            }
        }

        // Calculate total content height with 6px row gap
        totalContentHeight = 0;
        for (var r = 0; r < rows.size(); r++) {
            totalContentHeight += rows[r].rowHeight + 6;
        }

        var max = getMaxScroll();
        if (scrollY > max) {
            scrollY = max;
        }
        if (scrollY < 0) {
            scrollY = 0;
        }

        ensureValidSelection();
    }

    private function ensureValidSelection() as Void {
        if (rows.size() == 0) {
            selectedIndex = 0;
            return;
        }

        if (selectedIndex >= rows.size()) {
            selectedIndex = rows.size() - 1;
        }

        // If landing on a header, find next item (or previous)
        if (rows[selectedIndex].isHeader) {
            var found = false;
            for (var i = selectedIndex + 1; i < rows.size(); i++) {
                if (!rows[i].isHeader) {
                    selectedIndex = i;
                    found = true;
                    break;
                }
            }
            if (!found) {
                for (var i = selectedIndex - 1; i >= 0; i--) {
                    if (!rows[i].isHeader) {
                        selectedIndex = i;
                        break;
                    }
                }
            }
        }
        snapScrollToSelection();
    }

    function onUpdate(dc as Graphics.Dc) as Void {
        // Deep AMOLED Black
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();

        if (isLoading) {
            drawHeader(dc);
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                _screenWidth / 2,
                _screenHeight / 2,
                getMainFont(),
                _cachedLoading,
                Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
            );
            return;
        }

        if (rows.size() == 0) {
            drawHeader(dc);
            dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
            var msg = (statusMessage != null && statusMessage.length() > 0) ? statusMessage : _cachedEmpty;
            dc.drawText(
                _screenWidth / 2,
                _screenHeight / 2,
                getMainFont(),
                msg,
                Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
            );
            return;
        }

        // 1. Draw Visible Rows (natural clipping via header overlay for smooth 60FPS)
        var startX = (_screenWidth * 0.08).toNumber();
        var rowWidth = (_screenWidth * 0.84).toNumber();
        var curY = _headerHeight + 6 - scrollY;

        for (var i = 0; i < rows.size(); i++) {
            var row = rows[i];
            var rHeight = row.rowHeight;

            // Only draw rows intersecting the screen
            if (curY + rHeight >= _headerHeight && curY <= _screenHeight - 8) {
                if (row.isHeader) {
                    drawCategoryHeader(dc, row, startX, curY, rowWidth, rHeight);
                } else if (row.item != null) {
                    var isFocused = (i == selectedIndex);
                    drawItemRow(dc, row.item, startX, curY, rowWidth, rHeight, isFocused);
                }
            }

            curY += rHeight + 6;
            if (curY > _screenHeight) {
                break;
            }
        }

        // 2. Scroll Indicator on the right edge
        drawScrollIndicator(dc);

        // 3. Persistent Fixed Header (drawn last so it covers any row scrolling underneath)
        drawHeader(dc);
    }

    private function drawHeader(dc as Graphics.Dc) as Void {
        var totalRem = 0;
        var totalCount = 0;
        for (var c = 0; c < categories.size(); c++) {
            totalRem += categories[c].remainingCount;
            totalCount += categories[c].totalCount;
        }

        // Opaque AMOLED Black background to cleanly cover scrolling rows
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.fillRectangle(0, 0, _screenWidth, _headerHeight);

        // Title: Y = 16
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            _screenWidth / 2,
            16,
            getMainFont(),
            _cachedTitle,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Subtitle: Y = 50 ("X/Y נותרו")
        dc.setColor(0x94a3b8, Graphics.COLOR_TRANSPARENT);
        var subText = totalRem + "/" + totalCount + " " + _cachedRemSuffix;
        dc.drawText(
            _screenWidth / 2,
            50,
            getSmallFont(),
            subText,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Header separator line at Y = 80
        dc.setColor(0x1e293b, Graphics.COLOR_TRANSPARENT);
        dc.drawLine((_screenWidth * 0.20).toNumber(), 80, (_screenWidth * 0.80).toNumber(), 80);
    }

    private function drawCategoryHeader(
        dc as Graphics.Dc,
        row as GroceryRow,
        x as Number,
        y as Number,
        width as Number,
        height as Number
    ) as Void {
        var rightMargin = x + width - 6;
        var leftMargin = x + 6;
        var textY = y + 14;

        // Subtle divider line above category
        dc.setColor(0x1e293b, Graphics.COLOR_TRANSPARENT);
        dc.drawLine(x, y + 2, x + width, y + 2);

        // 1. Category Count (e.g. "10/11") on the LEFT
        dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            leftMargin,
            textY,
            getSmallFont(),
            row.headerCount,
            Graphics.TEXT_JUSTIFY_LEFT
        );

        // 2. Category Title on the RIGHT - safely truncated so it NEVER cuts the count on the left!
        var countW = dc.getTextWidthInPixels(row.headerCount, getSmallFont());
        var maxTitleW = (rightMargin - leftMargin) - countW - 16;
        if (maxTitleW < 20) {
            maxTitleW = 20;
        }

        if (row.fittedTitle.length() == 0) {
            row.fittedTitle = truncateStringToWidth(dc, row.headerTitle, getSmallFont(), maxTitleW);
        }

        dc.setColor(0x38bdf8, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            rightMargin,
            textY,
            getSmallFont(),
            row.fittedTitle,
            Graphics.TEXT_JUSTIFY_RIGHT
        );
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
        // Selection highlight box
        if (isFocused) {
            dc.setColor(0x13233c, Graphics.COLOR_TRANSPARENT);
            dc.fillRoundedRectangle(x - 4, y + 2, width + 8, height - 4, 8);
            dc.setColor(0x0284c7, Graphics.COLOR_TRANSPARENT);
            dc.drawRoundedRectangle(x - 4, y + 2, width + 8, height - 4, 8);
            dc.setColor(0x38bdf8, Graphics.COLOR_TRANSPARENT);
            dc.fillRoundedRectangle(x + width, y + 6, 3, height - 12, 2);
        }

        var rightMargin = x + width - 12;
        var leftMargin = x + 6;
        var availWidth = rightMargin - leftMargin;

        var hasNote = (item.shapedNote.length() > 0);
        var hasQuantity = (item.shapedQuantity.length() > 0);

        var fontH = dc.getFontHeight(getMainFont());
        var nameY = hasNote ? (y + 6) : (y + (height - fontH) / 2);
        var noteY = y + 44;

        // Colors
        var nameColor;
        var grayColor;
        if (item.isChecked) {
            nameColor = 0x64748b;
            grayColor = 0x475569;
        } else if (isFocused) {
            nameColor = Graphics.COLOR_WHITE;
            grayColor = 0x94a3b8;
        } else {
            nameColor = 0xe2e8f0;
            grayColor = 0x94a3b8;
        }

        // 1. Quantity on the LEFT
        var qtyW = 0;
        if (hasQuantity) {
            qtyW = dc.getTextWidthInPixels(item.shapedQuantity, getSmallFont());
            var maxQtyW = (availWidth * 0.38).toNumber();
            if (qtyW > maxQtyW) {
                item.shapedQuantity = truncateStringToWidth(dc, item.shapedQuantity, getSmallFont(), maxQtyW);
                qtyW = dc.getTextWidthInPixels(item.shapedQuantity, getSmallFont());
            }

            dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                leftMargin,
                nameY,
                getSmallFont(),
                item.shapedQuantity,
                Graphics.TEXT_JUSTIFY_LEFT
            );
        }

        // 2. Item Name on the RIGHT - safely truncated so it never overlaps quantity!
        var maxNameW = availWidth - (hasQuantity ? (qtyW + 14) : 0);
        if (maxNameW < 30) {
            maxNameW = 30;
        }

        if (item.fittedName.length() == 0) {
            item.fittedName = truncateStringToWidth(dc, item.shapedName, getMainFont(), maxNameW);
            item.nameWidth = dc.getTextWidthInPixels(item.fittedName, getMainFont());
        }

        dc.setColor(nameColor, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            rightMargin,
            nameY,
            getMainFont(),
            item.fittedName,
            Graphics.TEXT_JUSTIFY_RIGHT
        );

        // 3. Note directly underneath item name with generous vertical gap
        if (hasNote) {
            if (item.fittedNote.length() == 0) {
                item.fittedNote = truncateStringToWidth(dc, item.shapedNote, getSmallFont(), availWidth);
                item.noteWidth = dc.getTextWidthInPixels(item.fittedNote, getSmallFont());
            }

            dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                rightMargin,
                noteY,
                getSmallFont(),
                item.fittedNote,
                Graphics.TEXT_JUSTIFY_RIGHT
            );
        }

        // 4. Strikethrough line: positioned EXACTLY in the vertical center of the letters!
        if (item.isChecked) {
            dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth(2);

            var strikeY = nameY + (fontH / 2);
            dc.drawLine(rightMargin, strikeY, rightMargin - item.nameWidth, strikeY);

            // Strikethrough for note if present
            if (hasNote) {
                var noteH = dc.getFontHeight(getSmallFont());
                var noteStrikeY = noteY + (noteH / 2);
                dc.drawLine(rightMargin, noteStrikeY, rightMargin - item.noteWidth, noteStrikeY);
            }

            dc.setPenWidth(1);
        }
    }

    private function drawScrollIndicator(dc as Graphics.Dc) as Void {
        var maxScroll = getMaxScroll();
        if (maxScroll <= 0) {
            return;
        }

        var indicatorHeight = 36;
        var trackHeight = _screenHeight * 0.40;
        var trackY = _screenHeight * 0.30;
        var progress = scrollY.toFloat() / maxScroll.toFloat();
        if (progress > 1.0) {
            progress = 1.0;
        } else if (progress < 0.0) {
            progress = 0.0;
        }
        var indicatorY = trackY + (progress * (trackHeight - indicatorHeight)).toNumber();

        dc.setColor(0x334155, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(_screenWidth - 8, indicatorY, 3, indicatorHeight, 2);
    }

    // Navigation and Selection: Moves the blue highlight item by item, with screen locked to it
    function selectNextItem() as Void {
        if (rows.size() == 0) {
            return;
        }

        for (var i = selectedIndex + 1; i < rows.size(); i++) {
            if (!rows[i].isHeader && rows[i].item != null) {
                selectedIndex = i;
                snapScrollToSelection();
                WatchUi.requestUpdate();
                return;
            }
        }
    }

    function selectPreviousItem() as Void {
        if (rows.size() == 0) {
            return;
        }

        for (var i = selectedIndex - 1; i >= 0; i--) {
            if (!rows[i].isHeader && rows[i].item != null) {
                selectedIndex = i;
                snapScrollToSelection();
                WatchUi.requestUpdate();
                return;
            }
        }
    }

    function scrollDown() as Void {
        selectNextItem();
    }

    function scrollUp() as Void {
        selectPreviousItem();
    }

    function snapScrollToSelection() as Void {
        if (rows.size() == 0 || selectedIndex < 0 || selectedIndex >= rows.size()) {
            return;
        }
        var accY = 0;
        for (var i = 0; i < rows.size(); i++) {
            if (i == selectedIndex) {
                var itemCenter = accY + (rows[i].rowHeight / 2);
                scrollY = itemCenter - 140;
                var max = getMaxScroll();
                if (scrollY > max) { scrollY = max; }
                if (scrollY < 0) { scrollY = 0; }
                return;
            }
            accY += rows[i].rowHeight + 6;
        }
    }

    function getSelectedItem() as GroceryItem? {
        if (selectedIndex >= 0 && selectedIndex < rows.size()) {
            return rows[selectedIndex].item;
        }
        return null;
    }

    function getItemAtCoordinates(touchY as Number) as GroceryItem? {
        if (touchY < _headerHeight || touchY > _screenHeight - 10 || rows.size() == 0) {
            return null;
        }

        var curY = _headerHeight + 6 - scrollY;
        for (var i = 0; i < rows.size(); i++) {
            var row = rows[i];
            var rHeight = row.rowHeight;

            if (touchY >= curY && touchY <= curY + rHeight) {
                if (!row.isHeader && row.item != null) {
                    selectedIndex = i;
                    snapScrollToSelection();
                    return row.item;
                }
                return null;
            }

            curY += rHeight + 6;
        }

        return null;
    }

    function onItemToggled(item as GroceryItem) as Void {
        // When item is checked, rebuild rows so it automatically moves to the bottom of the category!
        rebuildRows();
        WatchUi.requestUpdate();
    }

    function setCategories(newCategories as Array<GroceryCategoryData>, msg as String?) as Void {
        categories = newCategories;
        isLoading = false;
        statusMessage = msg;
        rebuildRows();
        WatchUi.requestUpdate();
    }
}
