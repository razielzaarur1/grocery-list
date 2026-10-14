import Toybox.Lang;
import Toybox.StringUtil;

// BidiHelper: Handles Right-to-Left (RTL) visual shaping for Hebrew on Garmin Connect IQ
class BidiHelper {

    // Check if character is in Hebrew Unicode block (0x0590 - 0x05FF)
    static function isHebrewChar(c as Char) as Boolean {
        var code = c.toNumber();
        return (code >= 0x0590 && code <= 0x05FF);
    }

    // Shapes a Hebrew string so it renders correctly on Garmin's LTR canvas
    static function shapeHebrew(text as String?) as String {
        if (text == null || text.length() == 0) {
            return "";
        }

        var hasHebrew = false;
        var chars = text.toCharArray();
        for (var i = 0; i < chars.size(); i++) {
            if (isHebrewChar(chars[i])) {
                hasHebrew = true;
                break;
            }
        }

        // If no Hebrew characters, return as-is
        if (!hasHebrew) {
            return text;
        }

        // Reverse the string for visual RTL display on Garmin
        var reversed = new [chars.size()];
        var len = chars.size();
        for (var i = 0; i < len; i++) {
            var ch = chars[len - 1 - i];
            // Swap parentheses / brackets for proper RTL mirroring
            if (ch == '(') {
                reversed[i] = ')';
            } else if (ch == ')') {
                reversed[i] = '(';
            } else if (ch == '[') {
                reversed[i] = ']';
            } else if (ch == ']') {
                reversed[i] = '[';
            } else {
                reversed[i] = ch;
            }
        }

        return StringUtil.charArrayToString(reversed);
    }
}
