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
    private var _cachedHeaderSubtitle as String = "";
    private var _rowsMeasured as Boolean = false;

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
        var oldScroll = scrollY;
        scrollY += delta;
        var max = getMaxScroll();
        if (scrollY > max) {
            scrollY = max;
        }
        if (scrollY < 0) {
            scrollY = 0;
        }
        if (scrollY != oldScroll) {
            updateSelectionFromScroll();
            WatchUi.requestUpdate();
        }
    }

    function updateSelectionFromScroll() as Void {
        if (rows.size() == 0) {
            return;
        }

        // When scrollY == 0, targetY is 165 (first item center).
        // As scrollY increases, targetY smoothly moves to 235 (screen center).
        var targetY = 165 + (scrollY > 70 ? 70 : scrollY);

        var maxScroll = getMaxScroll();
        if (maxScroll > 0) {
            var distToBottom = maxScroll - scrollY;
            if (distToBottom < 70) {
                targetY += (70 - distToBottom);
            }
        }

        var curY = _headerHeight + 6 - scrollY;
        var bestIndex = -1;
        var minDistance = 999999;

        for (var i = 0; i < rows.size(); i++) {
            var row = rows[i];
            var rHeight = row.rowHeight;
            if (!row.isHeader && row.item != null) {
                var rowCenter = curY + (rHeight / 2);
                var diff = rowCenter - targetY;
                var dist = diff < 0 ? -diff : diff;
                if (dist < minDistance) {
                    minDistance = dist;
                    bestIndex = i;
                }
            }
            curY += rHeight + 6;
        }

        if (bestIndex != -1 && bestIndex != selectedIndex) {
            selectedIndex = bestIndex;
        }
    }

    // Rebuilds rows: Active categories first, Completed categories to the bottom!
    // Inside each category: Unchecked items first, Checked items at the bottom.
    function rebuildRows() as Void {
        rows = [] as Array<GroceryRow>;
        _rowsMeasured = false;

        var totalRem = 0;
        var totalCount = 0;

        var activeCats = [] as Array<GroceryCategoryData>;
        var completedCats = [] as Array<GroceryCategoryData>;

        for (var c = 0; c < categories.size(); c++) {
            var cat = categories[c];
            if (cat.items.size() == 0) {
                continue;
            }

            var uncheckCount = 0;
            for (var i = 0; i < cat.items.size(); i++) {
                if (!cat.items[i].isChecked) {
                    uncheckCount++;
                }
            }

            cat.remainingCount = uncheckCount;
            cat.totalCount = cat.items.size();
            totalRem += cat.remainingCount;
            totalCount += cat.totalCount;

            if (cat.remainingCount > 0) {
                activeCats.add(cat);
            } else {
                completedCats.add(cat);
            }
        }

        _cachedHeaderSubtitle = totalRem + "/" + totalCount + " " + _cachedRemSuffix;

        // 1. Add all active categories first
        for (var a = 0; a < activeCats.size(); a++) {
            addCategoryRows(activeCats[a]);
        }

        // 2. Add all completed categories at the bottom!
        for (var d = 0; d < completedCats.size(); d++) {
            addCategoryRows(completedCats[d]);
        }

        // Default initial height calculation
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

    private function addCategoryRows(cat as GroceryCategoryData) as Void {
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
                if (!rows[i].isHeader && rows[i].item != null) {
                    selectedIndex = i;
                    found = true;
                    break;
                }
            }
            if (!found) {
                for (var i = selectedIndex - 1; i >= 0; i--) {
                    if (!rows[i].isHeader && rows[i].item != null) {
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

        var rowWidth = (_screenWidth * 0.84).toNumber();

        // Pre-calculate exact multiline layout on first frame after data change (0 text computations in drag frames!)
        if (!_rowsMeasured && rows.size() > 0) {
            var availW = rowWidth - 18;
            var mainF = getMainFont();
            var smallF = getSmallFont();

            totalContentHeight = 0;
            for (var r = 0; r < rows.size(); r++) {
                rows[r].measure(dc, availW, mainF, smallF);
                totalContentHeight += rows[r].rowHeight + 6;
            }
            _rowsMeasured = true;
        }

        // 1. Draw Visible Rows (natural clipping via header overlay for smooth 60FPS)
        var startX = (_screenWidth * 0.08).toNumber();
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
                    drawItemRow(dc, row, startX, curY, rowWidth, rHeight, isFocused);
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
        dc.drawText(
            _screenWidth / 2,
            50,
            getSmallFont(),
            _cachedHeaderSubtitle,
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
        var smallFont = getSmallFont();
        var smallH = dc.getFontHeight(smallFont);

        // Subtle divider line above category
        dc.setColor(0x1e293b, Graphics.COLOR_TRANSPARENT);
        dc.drawLine(x, y + 2, x + width, y + 2);

        // 1. Category Count on the LEFT (vertically centered in header row)
        var countY = y + (height - smallH) / 2;
        dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
        dc.drawText(
            leftMargin,
            countY,
            smallFont,
            row.headerCount,
            Graphics.TEXT_JUSTIFY_LEFT
        );

        // 2. Category Title on the RIGHT (multiline wrapped if needed)
        dc.setColor(0x38bdf8, Graphics.COLOR_TRANSPARENT);
        var curY = (row.headerLines.size() <= 1) ? (y + 14) : (y + 8);
        for (var l = 0; l < row.headerLines.size(); l++) {
            dc.drawText(
                rightMargin,
                curY,
                smallFont,
                row.headerLines[l],
                Graphics.TEXT_JUSTIFY_RIGHT
            );
            curY += smallH + 2;
        }
    }

    private function drawItemRow(
        dc as Graphics.Dc,
        row as GroceryRow,
        x as Number,
        y as Number,
        width as Number,
        height as Number,
        isFocused as Boolean
    ) as Void {
        var item = row.item;
        if (item == null) {
            return;
        }

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

        var mainFont = getMainFont();
        var smallFont = getSmallFont();
        var mainH = dc.getFontHeight(mainFont);
        var smallH = dc.getFontHeight(smallFont);

        var hasNote = (row.noteLines.size() > 0);
        var hasQuantity = (item.shapedQuantity.length() > 0);

        var nameBlockH = (row.nameLines.size() * mainH) + ((row.nameLines.size() - 1) * 3);
        var nameStartY = hasNote ? (y + 8) : (y + (height - nameBlockH) / 2);

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
        if (hasQuantity) {
            dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
            dc.drawText(
                leftMargin,
                nameStartY,
                smallFont,
                item.shapedQuantity,
                Graphics.TEXT_JUSTIFY_LEFT
            );
        }

        // 2. Item Name Lines on the RIGHT
        dc.setColor(nameColor, Graphics.COLOR_TRANSPARENT);
        var curNameY = nameStartY;
        for (var i = 0; i < row.nameLines.size(); i++) {
            dc.drawText(
                rightMargin,
                curNameY,
                mainFont,
                row.nameLines[i],
                Graphics.TEXT_JUSTIFY_RIGHT
            );

            // Strikethrough line per name line if checked
            if (item.isChecked) {
                dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
                dc.setPenWidth(2);
                var strikeY = curNameY + (mainH / 2);
                var lineW = (i < row.nameLineWidths.size()) ? row.nameLineWidths[i] : 40;
                dc.drawLine(rightMargin, strikeY, rightMargin - lineW, strikeY);
                dc.setColor(nameColor, Graphics.COLOR_TRANSPARENT);
                dc.setPenWidth(1);
            }

            curNameY += mainH + 3;
        }

        // 3. Note Lines on the RIGHT (12px generous gap below name block)
        if (hasNote) {
            dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
            var curNoteY = nameStartY + nameBlockH + 12;
            for (var j = 0; j < row.noteLines.size(); j++) {
                dc.drawText(
                    rightMargin,
                    curNoteY,
                    smallFont,
                    row.noteLines[j],
                    Graphics.TEXT_JUSTIFY_RIGHT
                );

                // Strikethrough for note if checked
                if (item.isChecked) {
                    dc.setColor(0x64748b, Graphics.COLOR_TRANSPARENT);
                    dc.setPenWidth(2);
                    var noteStrikeY = curNoteY + (smallH / 2);
                    var noteLineW = (j < row.noteLineWidths.size()) ? row.noteLineWidths[j] : 30;
                    dc.drawLine(rightMargin, noteStrikeY, rightMargin - noteLineW, noteStrikeY);
                    dc.setColor(grayColor, Graphics.COLOR_TRANSPARENT);
                    dc.setPenWidth(1);
                }

                curNoteY += smallH + 2;
            }
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

    // Navigation and Selection (Physical Buttons & D-pad)
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

    function setCategories(newCategories as Array<GroceryCategoryData>?, msg as String?) as Void {
        if (newCategories != null) {
            categories = newCategories;
            _rowsMeasured = false;
            rebuildRows();
        }
        isLoading = false;
        statusMessage = msg;
        WatchUi.requestUpdate();
    }
}
