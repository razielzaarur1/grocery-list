import Toybox.Lang;
import Toybox.Graphics;

class GroceryRow {
    var isHeader as Boolean = false;
    var categoryId as Number = 0;
    var headerTitle as String = "";
    var headerCount as String = "";
    var item as GroceryItem? = null;
    var rowHeight as Number = 54;

    // Multiline pre-calculated layout data for 60fps rendering
    var isMeasured as Boolean = false;
    var headerLines as Array<String> = [] as Array<String>;
    var nameLines as Array<String> = [] as Array<String>;
    var nameLineWidths as Array<Number> = [] as Array<Number>;
    var noteLines as Array<String> = [] as Array<String>;
    var noteLineWidths as Array<Number> = [] as Array<Number>;
    var qtyWidth as Number = 0;
    var countWidth as Number = 0;

    function initializeAsHeader(catId as Number, title as String, countStr as String) {
        isHeader = true;
        categoryId = catId;
        headerTitle = BidiHelper.shapeHebrew(title);
        headerCount = countStr;
        item = null;
        rowHeight = 42;
        isMeasured = false;
        headerLines = [] as Array<String>;
        nameLines = [] as Array<String>;
        nameLineWidths = [] as Array<Number>;
        noteLines = [] as Array<String>;
        noteLineWidths = [] as Array<Number>;
        qtyWidth = 0;
        countWidth = 0;
    }

    function initializeAsItem(groceryItem as GroceryItem) {
        isHeader = false;
        item = groceryItem;
        categoryId = groceryItem.categoryId;
        headerTitle = "";
        headerCount = "";
        var hasNote = (groceryItem.note.length() > 0);
        rowHeight = hasNote ? 76 : 54;
        isMeasured = false;
        headerLines = [] as Array<String>;
        nameLines = [] as Array<String>;
        nameLineWidths = [] as Array<Number>;
        noteLines = [] as Array<String>;
        noteLineWidths = [] as Array<Number>;
        qtyWidth = 0;
        countWidth = 0;
    }

    function measure(
        dc as Graphics.Dc,
        availWidth as Number,
        mainFont as Graphics.FontDefinition,
        smallFont as Graphics.FontDefinition
    ) as Void {
        if (isMeasured) {
            return;
        }

        var mainH = dc.getFontHeight(mainFont);
        var smallH = dc.getFontHeight(smallFont);

        if (isHeader) {
            countWidth = dc.getTextWidthInPixels(headerCount, smallFont);
            var maxTitleW = availWidth - countWidth - 16;
            if (maxTitleW < 40) {
                maxTitleW = 40;
            }
            headerLines = wrapText(dc, headerTitle, smallFont, maxTitleW);
            if (headerLines.size() <= 1) {
                rowHeight = 42;
            } else {
                rowHeight = 8 + (headerLines.size() * smallH) + ((headerLines.size() - 1) * 2) + 8;
            }
        } else if (item != null) {
            var hasQty = (item.shapedQuantity.length() > 0);
            var hasNote = (item.shapedNote.length() > 0);

            if (hasQty) {
                qtyWidth = dc.getTextWidthInPixels(item.shapedQuantity, smallFont);
                var maxQtyW = (availWidth * 0.35).toNumber();
                if (qtyWidth > maxQtyW) {
                    var qtyLines = wrapText(dc, item.shapedQuantity, smallFont, maxQtyW);
                    if (qtyLines.size() > 0) {
                        item.shapedQuantity = qtyLines[0];
                        qtyWidth = dc.getTextWidthInPixels(item.shapedQuantity, smallFont);
                    }
                }
            } else {
                qtyWidth = 0;
            }

            var maxNameW = availWidth - (hasQty ? (qtyWidth + 14) : 0);
            if (maxNameW < 40) {
                maxNameW = 40;
            }

            nameLines = wrapText(dc, item.shapedName, mainFont, maxNameW);
            nameLineWidths = [] as Array<Number>;
            for (var i = 0; i < nameLines.size(); i++) {
                nameLineWidths.add(dc.getTextWidthInPixels(nameLines[i], mainFont));
            }

            var nameBlockH = (nameLines.size() * mainH) + ((nameLines.size() - 1) * 3);

            if (hasNote) {
                noteLines = wrapText(dc, item.shapedNote, smallFont, availWidth);
                noteLineWidths = [] as Array<Number>;
                for (var j = 0; j < noteLines.size(); j++) {
                    noteLineWidths.add(dc.getTextWidthInPixels(noteLines[j], smallFont));
                }
                var noteBlockH = (noteLines.size() * smallH) + ((noteLines.size() - 1) * 2);
                rowHeight = 8 + nameBlockH + 12 + noteBlockH + 8;
            } else {
                noteLines = [] as Array<String>;
                noteLineWidths = [] as Array<Number>;
                var calcH = 8 + nameBlockH + 8;
                rowHeight = (calcH < 54) ? 54 : calcH;
            }
        }

        isMeasured = true;
    }

    private function wrapText(
        dc as Graphics.Dc,
        text as String,
        font as Graphics.FontDefinition,
        maxWidth as Number
    ) as Array<String> {
        var lines = [] as Array<String>;
        if (text == null || text.length() == 0) {
            return lines;
        }

        if (dc.getTextWidthInPixels(text, font) <= maxWidth) {
            lines.add(text);
            return lines;
        }

        var words = [] as Array<String>;
        var chars = text.toCharArray();
        var curWord = "";
        for (var i = 0; i < chars.size(); i++) {
            var ch = chars[i];
            if (ch == ' ') {
                if (curWord.length() > 0) {
                    words.add(curWord);
                    curWord = "";
                }
            } else {
                curWord += ch.toString();
            }
        }
        if (curWord.length() > 0) {
            words.add(curWord);
        }

        if (words.size() == 0) {
            lines.add(text);
            return lines;
        }

        var currentLine = "";
        for (var w = 0; w < words.size(); w++) {
            var word = words[w];
            var testLine = (currentLine.length() == 0) ? word : (currentLine + " " + word);

            if (dc.getTextWidthInPixels(testLine, font) <= maxWidth) {
                currentLine = testLine;
            } else {
                if (currentLine.length() > 0) {
                    lines.add(currentLine);
                    currentLine = word;
                } else {
                    lines.add(word);
                    currentLine = "";
                }
            }
        }
        if (currentLine.length() > 0) {
            lines.add(currentLine);
        }

        return lines;
    }
}
