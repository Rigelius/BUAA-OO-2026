import java.util.HashMap;
import java.util.Map;
import java.util.Scanner;

public class MainClass {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        FuncReg registry = new FuncReg();
        Parser parser = new Parser(registry);

        int n = Integer.parseInt(sc.nextLine().trim());
        for (int i = 0; i < n; i++) {
            parser.parseFuncDef(sc);
        }

        int m = Integer.parseInt(sc.nextLine().trim());
        for (int i = 0; i < m; i++) {
            parser.parseRecDef(sc);
        }

        Expr expr = parser.parseExprFromText(sc.nextLine());

        Map<String, Poly> vars = new HashMap<>();
        vars.put("x", Poly.X);
        vars.put("y", Poly.Y);

        Poly ans = expr.toPoly(vars);
        System.out.println(ans);
    }
}