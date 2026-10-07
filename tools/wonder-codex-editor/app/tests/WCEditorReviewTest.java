package nomanssave;
import java.nio.charset.StandardCharsets;
public final class WCEditorReviewTest {
 public static void main(String[] args)throws Exception{
  eY before=ff.b("{\"UserData\":18446744073709551615,\"Name\":\"Before\",\"Items\":[1,2]}".getBytes(StandardCharsets.UTF_8));
  eY after=before.bE();after.put("Name","After");after.d("Items").set(1,3);
  String result=WCEditorReview.describe(before,after);
  if(!result.startsWith("2 changed values"))throw new AssertionError(result);
  if(!result.contains("$.Name")||!result.contains("$.Items[1]"))throw new AssertionError("Missing paths");
  if(result.contains("UserData"))throw new AssertionError("Large integer falsely changed");
  if(!before.bz().contains("18446744073709551615"))throw new AssertionError("Original changed");
  if(!WCEditorReview.describe(before,before.bE()).startsWith("0 changed values"))throw new AssertionError("Copy must match");
  System.out.println("REVIEW_TEST PASS exact integers, paths, array deltas and no mutation");
 }
}
