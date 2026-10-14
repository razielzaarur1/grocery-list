import Toybox.Lang;

// BidiHelper: Returns text in natural order without inversion
class BidiHelper {

    static function shapeHebrew(text as String?) as String {
        if (text == null || text.length() == 0) {
            return "";
        }
        return text;
    }
}
