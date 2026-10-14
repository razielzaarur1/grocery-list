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

    private var _headerHeight as Number = 72;
    private var _screenWidth as Number = 454;
    private var _screenHeight as Number = 454;

    function initialize() {
        View.initialize();
    }

    function onLayout(dc as Graphics.Dc) as Void {
        _screenWidth = dc.getWidth();
        _screenHeight = dc.getHeight();
        _headerHeight = 72;
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

        // Calculate total content height
        totalContentHeight = 0;
        for (var r = 0; r < rows.size(); r++) {
            totalContentHeight += rows[r].rowHeight + 4;
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
    }

    function onUpdate(dc as Graphics.Dc) as Void {
        // Deep AMOLED Black
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();

        if (isLoading) {
            drawHeader(dc);
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            var loadText = WatchUi.loadResource(Rez.Strings.LoadingText) as String;
            dc.drawText(
                _screenWidth / 2,
                _screenHeight / 2,
                getMainFont(),
                loadText,
                Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
            );
            return;
        }

        if (rows.size() == 0) {
            drawHeader(dc);
            dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
            var emptyText = WatchUi.loadResource(Rez.Strings.EmptyText) as String;
            var msg = (statusMessage != null && statusMessage.length() > 0) ? statusMessage : emptyText;
            dc.drawText(
                _screenWidth / 2,
                _screenHeight / 2,
                getMainFont(),
                msg,
                Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER
            );
            return;
        }

        // 1. Draw Visible Rows with clipping to prevent any overlap outside content area
        var clipY = _headerHeight;
        var clipH = _screenHeight - _headerHeight - 12;
        dc.setClip(0, clipY, _screenWidth, clipH);

        var startX = (_screenWidth * 0.08).toNumber();
        var rowWidth = (_screenWidth * 0.84).toNumber();
        var curY = _headerHeight + 4 - scrollY;

        for (var i = 0; i < rows.size(); i++) {
            var row = rows[i];
            var rHeight = row.rowHeight;

            // Only draw if within visible screen bounds
            if (curY + rHeight >= _headerHeight && curY <= _screenHeight - 10) {
                if (row.isHeader) {
                    drawCategoryHeader(dc, row, startX, curY, rowWidth, rHeight);
                } else if (row.item != null) {
                    var isFocused = (i == selectedIndex);
                    drawItemRow(dc, row.item, startX, curY, rowWidth, rHeight, isFocused);
                }
            }

            curY += rHeight + 4;
        }

        dc.clearClip();

        // 2. Scroll Indicator on the right edge
        drawScrollIndicator(dc);

        // 3. Persistent Fixed Header (drawn last so rows scroll cleanly underneath it)
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

        // Title: Y = 14
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        var titleText = WatchUi.loadResource(Rez.Strings.AppName) as String;
        dc.drawText(
            _screenWidth / 2,
            14,
            getMainFont(),
            titleText,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Subtitle: "X/Y נותרו", Y = 42
        dc.setColor(0x94a3b8, Graphics.COLOR_TRANSPARENT);
        var remSuffix = WatchUi.loadResource(Rez.Strings.RemainingSuffix) as String;
        var subText = totalRem + "/" + totalCount + " " + remSuffix;
        dc.drawText(
            _screenWidth / 2,
            42,
            getSmallFont(),
            subText,
            Graphics.TEXT_JUSTIFY_CENTER
        );

        // Header separator
        dc.setColor(0x1e293b, Graphics.COLOR_TRANSPARENT);
        dc.drawLine((_screenWidth * 0.20).toNumber(), _headerHeight - 2, (_screenWidth * 0.80).toNumber(), _headerHeight - 2);
    }

    private function drawCategoryHeader(
        dc as Graphics.Dc,
        row as GroceryRow,
        x as Number,
        y as Number,
        width as Number,
        height as Number
    ) as Void {
        var rightMargin = x + width - 4;
        var leftMargin = x + 4;
        var textY = y + 9;

        // Subtle divider line above category
        dc.setColor(0x1e293b, Graphics.COLOR_TRANSPARENT);
        dc.drawLine(x, y + 2, x + width, y + 2);

        // Category Title on the RIGHT in stylish sky blue
        dc.setColor(0x38bdf8, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            rightMargin,
            textY,
            getSmallFont(),
            row.headerTitle,
            Graphics.TEXT_JUSTIFY_RIGHT
        );

        // Category Count (e.g. "10/11") on the LEFT
        dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            leftMargin,
            textY,
            getSmallFont(),
            row.headerCount,
            Graphics.TEXT_JUSTIFY_LEFT
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
        // Modern, subtle selection background and right accent bar
        if (isFocused) {
            // Soft rounded dark pill (blends smoothly into AMOLED black)
            dc.setColor(0x162032, Graphics.COLOR_TRANSPARENT);
            dc.fillRoundedRectangle(x - 4, y, width + 8, height - 2, 10);

            // Sleek vertical cyan accent indicator on the right edge
            dc.setColor(0x38bdf8, Graphics.COLOR_TRANSPARENT);
            dc.fillRoundedRectangle(x + width - 1, y + 6, 4, height - 14, 2);
        }

        var rightMargin = x + width - 12;
        var leftMargin = x + 6;

        var hasNote = (item.shapedNote.length() > 0);
        var hasQuantity = (item.shapedQuantity.length() > 0);

        var fontH = dc.getFontHeight(getMainFont());
        var nameY = hasNote ? (y + 4) : (y + (height - fontH) / 2);
        var noteY = nameY + fontH + 1;

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

        // 1. Item Name on the RIGHT
        dc.setColor(nameColor, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            rightMargin,
            nameY,
            getMainFont(),
            item.shapedName,
            Graphics.TEXT_JUSTIFY_RIGHT
        );

        // 2. Quantity on the LEFT
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

        // 3. Note directly underneath item name
        if (hasNote) {
            dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                rightMargin,
                noteY,
                getSmallFont(),
                item.shapedNote,
                Graphics.TEXT_JUSTIFY_RIGHT
            );
        }

        // 4. Strikethrough line: positioned EXACTLY in the vertical center of the letters!
        if (item.isChecked) {
            dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth(2);

            // Measure exact text pixel width
            var textWidth = dc.getTextWidthInPixels(item.shapedName, getMainFont());
            var strikeY = nameY + (fontH / 2);

            dc.drawLine(rightMargin, strikeY, rightMargin - textWidth, strikeY);

            // Strikethrough for note if present
            if (hasNote) {
                var noteWidth = dc.getTextWidthInPixels(item.shapedNote, getSmallFont());
                var noteH = dc.getFontHeight(getSmallFont());
                var noteStrikeY = noteY + (noteH / 2);
                dc.drawLine(rightMargin, noteStrikeY, rightMargin - noteWidth, noteStrikeY);
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

    // Navigation and Scrolling (Hardware Buttons & D-pad)
    function scrollDown() as Void {
        if (rows.size() == 0) {
            return;
        }

        // Find next item row (skip headers)
        for (var i = selectedIndex + 1; i < rows.size(); i++) {
            if (!rows[i].isHeader) {
                selectedIndex = i;
                ensureSelectionVisible();
                WatchUi.requestUpdate();
                return;
            }
        }
    }

    function scrollUp() as Void {
        if (rows.size() == 0) {
            return;
        }

        // Find previous item row (skip headers)
        for (var i = selectedIndex - 1; i >= 0; i--) {
            if (!rows[i].isHeader) {
                selectedIndex = i;
                ensureSelectionVisible();
                WatchUi.requestUpdate();
                return;
            }
        }
    }

    private function ensureSelectionVisible() as Void {
        var accY = 0;
        for (var i = 0; i < rows.size(); i++) {
            if (i == selectedIndex) {
                var itemTop = accY;
                var itemBottom = accY + rows[i].rowHeight;
                var visibleTop = scrollY;
                var visibleBottom = scrollY + (_screenHeight - _headerHeight - 20);

                if (itemTop < visibleTop) {
                    scrollY = itemTop;
                } else if (itemBottom > visibleBottom) {
                    scrollY = itemBottom - (_screenHeight - _headerHeight - 20);
                }
                var max = getMaxScroll();
                if (scrollY > max) { scrollY = max; }
                if (scrollY < 0) { scrollY = 0; }
                return;
            }
            accY += rows[i].rowHeight + 4;
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

        var curY = _headerHeight + 4 - scrollY;
        for (var i = 0; i < rows.size(); i++) {
            var row = rows[i];
            var rHeight = row.rowHeight;

            if (touchY >= curY && touchY <= curY + rHeight) {
                if (!row.isHeader && row.item != null) {
                    selectedIndex = i;
                    return row.item;
                }
                return null;
            }

            curY += rHeight + 4;
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
