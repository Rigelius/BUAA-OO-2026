public class Processor {
    public static String preprocess(String input) {
        String s = input.replaceAll("[ \\t]+", "");
        int len;
        do {
            len = s.length();
            s = s.replace("++", "+")
                .replace("+-", "-")
                .replace("-+", "-")
                .replace("--", "+");
        } while (s.length() != len);
        return s;
    }
}