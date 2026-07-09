public class Processor {
    public static String preprocess(String input) {
        String s = input.replaceAll("\\s+", "");
        while (s.contains("++") || s.contains("+-") || s.contains("-+") || s.contains("--")) {
            s = s.replace("++", "+");
            s = s.replace("+-", "-");
            s = s.replace("-+", "-");
            s = s.replace("--", "+");
        }
        if (s.startsWith("+")) {
            s = s.substring(1);
        }
        s = s.replace("(+", "(");
        s = s.replace("*+", "*");
        s = s.replace("^+", "^");
        return s;
    }
}