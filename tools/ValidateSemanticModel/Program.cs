using Microsoft.AnalysisServices.Tabular;
var path = args.Length == 1 ? args[0] : "powerbi/Turismo.SemanticModel/definition";
var database = TmdlSerializer.DeserializeDatabaseFromFolder(Path.GetFullPath(path));
var model = database.Model;
if (model.Tables.Count != 8 || model.Relationships.Count != 9 || model.Roles.Count != 8) throw new InvalidOperationException("The expected tables, relationships or province roles are missing.");
foreach (var relationship in model.Relationships.OfType<SingleColumnRelationship>())
{
    if (relationship.FromColumn is null || relationship.ToColumn is null || relationship.CrossFilteringBehavior != CrossFilteringBehavior.OneDirection) throw new InvalidOperationException("Invalid star schema relationship.");
}
foreach (var role in model.Roles)
{
    if (role.ModelPermission != ModelPermission.Read || role.TablePermissions.Count != 3) throw new InvalidOperationException("Unexpected role permissions.");
    var province = role.TablePermissions.Find("dim_province");
    if (province is null || !province.FilterExpression.Contains(role.Name)) throw new InvalidOperationException("The province filter is missing.");
    foreach (var tableName in new[] { "fact_markets_annual", "fact_region_monthly" })
        if (role.TablePermissions.Find(tableName)?.FilterExpression != "FALSE()") throw new InvalidOperationException("Regional data must not bypass a provincial role.");
}
if (model.Tables.Sum(table => table.Measures.Count) != 15) throw new InvalidOperationException("Missing analytical measures.");
Console.WriteLine($"Semantic model validated: {database.Model.Tables.Count} tables, {database.Model.Relationships.Count} relationships, {database.Model.Roles.Count} province roles.");
