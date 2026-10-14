import Toybox.Lang;
import Toybox.StringUtil;

// BidiHelper: Reverses Hebrew text for Garmin's LTR canvas while preserving numbers and symbols
class BidiHelper {

    static function isHebrewChar(c as Char) as Boolean {
        var code = c.toNumber();
        return (code >= 0x0590 && code <= 0x05FF);
    }

    static function shapeHebrew(text as String?) as String {
        if (text == null || text.length() == 0) {
            return "";
        }

        try {
            var chars = text.toCharArray();
            var len = chars.size();
            var hasHebrew = false;

            for (var i = 0; i < len; i++) {
                if (isHebrewChar(chars[i])) {
                    hasHebrew = true;
                    break;
                }
            }

            // If string doesn't contain any Hebrew, return decoded Unicode string as-is
            if (!hasHebrew) {
                return StringUtil.charArrayToString(chars);
            }

            // 1. Reverse characters and mirror brackets
            var reversed = new [len];
            for (var i = 0; i < len; i++) {
                var ch = chars[len - 1 - i];
                if (ch == '(') {
                    reversed[i] = ')';
                } else if (ch == ')') {
                    reversed[i] = '(';
                } else if (ch == '[') {
                    reversed[i] = ']';
                } else if (ch == ']') {
                    reversed[i] = '[';
                } else if (ch == '{') {
                    reversed[i] = '}';
                } else if (ch == '}') {
                    reversed[i] = '{';
                } else {
                    reversed[i] = ch;
                }
            }

            // 2. Re-reverse numeric digits so numbers read LTR (e.g. 19 stays 19, not 91)
            var numStart = -1;
            for (var i = 0; i <= len; i++) {
                var isDigit = false;
                if (i < len) {
                    var ch = reversed[i];
                    if (ch >= '0' && ch <= '9') {
                        isDigit = true;
                    }
                }

                if (isDigit) {
                    if (numStart == -1) {
                        numStart = i;
                    }
                } else {
                    if (numStart != -1) {
                        var numEnd = i - 1;
                        // Reverse digits between numStart and numEnd
                        while (numStart < numEnd) {
                            var tmp = reversed[numStart];
                            reversed[numStart] = reversed[numEnd];
                            reversed[numEnd] = tmp;
                            numStart++;
                            numEnd--;
                        }
                        numStart = -1;
                    }
                }
            }

            return StringUtil.charArrayToString(reversed);
        } catch (ex) {
            return text;
        }
    }
}
