import Toybox.Lang;
import Toybox.StringUtil;

// BidiHelper: Decodes UTF-8 into true Unicode characters for Garmin BMFont in natural order
class BidiHelper {

    static function shapeHebrew(text as String?) as String {
        if (text == null || text.length() == 0) {
            return "";
        }

        return text;
    }
}
